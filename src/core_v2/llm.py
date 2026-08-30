"""
Kioxus Core v2 — LLM 客户端
统一调用接口、多模型支持、流式输出

Phase 1: 基础HTTP调用 + 多provider
Phase 2: 流式输出 + 结构化输出 + 模型选择策略
"""

import json
import time
import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ModelRole(Enum):
    """模型角色"""
    DEFAULT = "default"      # 日常对话
    REASONING = "reasoning"  # 复杂推理
    COMPRESS = "compress"    # 压缩/Flush
    EMBEDDING = "embedding"  # 嵌入向量


@dataclass
class LLMMessage:
    """LLM消息"""
    role: str
    content: str


@dataclass
class LLMResponse:
    """LLM响应"""
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    latency_ms: float = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """Provider配置"""
    name: str
    api_url: str
    api_key: str
    model: str
    api_keys: List[str] = field(default_factory=list)  # 多Key支持
    role: ModelRole = ModelRole.DEFAULT
    max_tokens: int = 4096
    temperature: float = 0.7
    headers: Dict = field(default_factory=dict)
    # 轮换状态
    _current_key_idx: int = field(default=0, repr=False)
    _key_failures: Dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        if not self.api_keys and self.api_key:
            self.api_keys = [self.api_key]

    @property
    def current_api_key(self) -> str:
        if self.api_keys:
            return self.api_keys[self._current_key_idx % len(self.api_keys)]
        return self.api_key

    def rotate_key(self):
        import time
        now = time.time()
        for i in range(len(self.api_keys)):
            idx = (self._current_key_idx + 1 + i) % len(self.api_keys)
            last_fail = self._key_failures.get(idx, 0)
            if now - last_fail > 60:
                self._current_key_idx = idx
                return self.api_keys[idx]
        return None

    def mark_key_failed(self):
        import time
        self._key_failures[self._current_key_idx] = time.time()

    def mark_key_success(self):
        self._key_failures.pop(self._current_key_idx, None)


# ============== Provider 实现 ==============

class BaseProvider:
    """Provider基类"""

    def __init__(self, config: ProviderConfig):
        """__init__"""
        self.config = config

    def chat(self, messages: List[LLMMessage], stream: bool = False) -> LLMResponse:
        """chat"""
        raise NotImplementedError

    def _format_messages(self, messages: List[LLMMessage]) -> List[Dict]:
        """_format_messages"""
        result = []
        for m in messages:
            if isinstance(m, dict):
                result.append(m)
            else:
                result.append({"role": m.role, "content": m.content})
        return result


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI兼容API（支持大多数国产模型）"""

    # 限流状态码
    RATE_LIMIT_CODES = {429, 529}

    def chat(self, messages: List[LLMMessage], stream: bool = False) -> LLMResponse:
        """chat — 支持多Key轮换和限流重试"""
        import urllib.request

        max_retries = len(self.config.api_keys) if self.config.api_keys else 1
        last_error = None

        for attempt in range(max_retries):
            current_key = self.config.current_api_key
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {current_key}",
                **self.config.headers,
            }

            payload = {
                "model": self.config.model,
                "messages": self._format_messages(messages),
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "stream": False,
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(self.config.api_url, data=data, headers=headers, method="POST")

            start = time.time()
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                latency = (time.time() - start) * 1000

                content = body["choices"][0]["message"]["content"]
                usage = body.get("usage", {})

                # 成功，标记Key可用
                if hasattr(self.config, 'mark_key_success'):
                    self.config.mark_key_success()

                return LLMResponse(
                    content=content,
                    model=self.config.model,
                    provider=self.config.name,
                    tokens_used=usage.get("total_tokens", 0),
                    latency_ms=latency,
                    metadata={"status": "ok", "attempt": attempt + 1},
                )
            except urllib.error.HTTPError as e:
                latency = (time.time() - start) * 1000
                last_error = e

                if e.code in self.RATE_LIMIT_CODES and self.config.api_keys and len(self.config.api_keys) > 1:
                    # 限流，轮换Key重试
                    if hasattr(self.config, 'mark_key_failed'):
                        self.config.mark_key_failed()
                    new_key = self.config.rotate_key()
                    if new_key:
                        logger.warning(f"[{self.config.name}] 限流 {e.code}，轮换Key重试 ({attempt+1}/{max_retries})")
                        continue

                logger.error(f"LLM调用失败 [{self.config.name}]: {e}")
                return LLMResponse(
                    content=f"[LLM调用失败: {e}]",
                    model=self.config.model,
                    provider=self.config.name,
                    latency_ms=latency,
                    metadata={"status": "error", "code": e.code, "error": str(e)},
                )
            except Exception as e:
                latency = (time.time() - start) * 1000
                last_error = e
                logger.error(f"LLM调用失败 [{self.config.name}]: {e}")
                return LLMResponse(
                    content=f"[LLM调用失败: {e}]",
                    model=self.config.model,
                    provider=self.config.name,
                    latency_ms=latency,
                    metadata={"status": "error", "error": str(e)},
                )

        # 所有重试都失败
        return LLMResponse(
            content=f"[LLM调用失败: 所有Key均限流 ({max_retries}次尝试)]",
            model=self.config.model,
            provider=self.config.name,
            metadata={"status": "error", "error": "all_keys_rate_limited"},
        )


class MockProvider(BaseProvider):
    """测试用Mock Provider"""

    def chat(self, messages: List[LLMMessage], stream: bool = False) -> LLMResponse:
        """chat"""
        last_msg = messages[-1]
        if isinstance(last_msg, dict):
            content = last_msg.get("content", "")
        else:
            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        return LLMResponse(
            content=f"[Mock] {content[:100]}",
            model="mock",
            provider="mock",
            tokens_used=0,
            latency_ms=1,
            metadata={"status": "mock"},
        )


# ============== LLM 客户端 ==============

class LLMClient:
    """统一LLM客户端"""

    def __init__(self):
        """__init__"""
        self._providers: Dict[str, BaseProvider] = {}
        self._role_map: Dict[ModelRole, str] = {}  # role -> provider_name
        self._default_role = ModelRole.DEFAULT

    def register_provider(self, config: ProviderConfig):
        """注册一个Provider"""
        if config.name == "mock":
            provider = MockProvider(config)
        else:
            provider = OpenAICompatibleProvider(config)

        self._providers[config.name] = provider
        self._role_map[config.role] = config.name
        logger.info(f"Registered provider: {config.name} ({config.model})")

    def register_mock(self):
        """注册Mock Provider（用于测试）"""
        config = ProviderConfig(
            name="mock",
            api_url="",
            api_key="",
            model="mock",
            role=ModelRole.DEFAULT,
        )
        self.register_provider(config)

    def get_provider(self, role: ModelRole = None) -> BaseProvider:
        """获取指定角色的Provider"""
        role = role or self._default_role
        provider_name = self._role_map.get(role)
        if provider_name and provider_name in self._providers:
            return self._providers[provider_name]
        # 回退到DEFAULT
        provider_name = self._role_map.get(ModelRole.DEFAULT)
        if provider_name and provider_name in self._providers:
            return self._providers[provider_name]
        raise ValueError(f"No provider registered for role {role}")

    def generate(
        self,
        messages: List[LLMMessage],
        role: ModelRole = None,
        stream: bool = False,
    ) -> LLMResponse:
        """生成响应 — 支持Model Failover（主Provider失败自动切备用）"""
        primary_name = self._role_map.get(role or self._default_role)
        provider_order = []

        # 先尝试指定角色的Provider
        if primary_name and primary_name in self._providers:
            provider_order.append(primary_name)

        # 再尝试DEFAULT角色
        default_name = self._role_map.get(ModelRole.DEFAULT)
        if default_name and default_name not in provider_order:
            provider_order.append(default_name)

        # 最后尝试所有其他Provider作为备用
        for name in self._providers:
            if name not in provider_order and name != "mock":
                provider_order.append(name)

        last_response = None
        for pname in provider_order:
            provider = self._providers[pname]
            response = provider.chat(messages, stream=stream)
            if response.metadata.get("status") == "ok":
                return response
            last_response = response
            logger.warning(f"Provider {pname} failed, trying next...")

        # 所有Provider都失败
        if last_response:
            return last_response
        raise ValueError("No provider available")

    def generate_from_context(
        self,
        system_prompt: str,
        user_message: str,
        history: List[Dict] = None,
        role: ModelRole = None,
    ) -> LLMResponse:
        """便捷方法：从上下文字符串生成"""
        messages = []

        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))

        if history:
            for h in history:
                messages.append(LLMMessage(role=h["role"], content=h["content"]))

        messages.append(LLMMessage(role="user", content=user_message))

        return self.generate(messages, role=role)

    def select_role(self, intent: str, complexity: str = "simple") -> ModelRole:
        """根据任务选择模型角色"""
        if intent == "command":
            return ModelRole.COMPRESS  # 简单任务用小模型
        if complexity == "complex":
            return ModelRole.REASONING
        return self._default_role

    @property
    def available_providers(self) -> List[str]:
        """available_providers"""
        return list(self._providers.keys())

    @property
    def available_roles(self) -> List[ModelRole]:
        """available_roles"""
        return list(self._role_map.keys())


# ============== 单例 ==============

_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """get_llm_client"""
    global _instance
    if _instance is None:
        _instance = LLMClient()
    return _instance


def reset_llm_client():
    """重置单例（测试用）"""
    global _instance
    _instance = None
