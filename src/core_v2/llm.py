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
    role: ModelRole = ModelRole.DEFAULT
    max_tokens: int = 4096
    temperature: float = 0.7
    headers: Dict = field(default_factory=dict)


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

    def chat(self, messages: List[LLMMessage], stream: bool = False) -> LLMResponse:
        """chat"""
        import urllib.request

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            **self.config.headers,
        }

        payload = {
            "model": self.config.model,
            "messages": self._format_messages(messages),
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False,  # Phase 1 不做流式
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

            return LLMResponse(
                content=content,
                model=self.config.model,
                provider=self.config.name,
                tokens_used=usage.get("total_tokens", 0),
                latency_ms=latency,
                metadata={"status": "ok"},
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"LLM调用失败 [{self.config.name}]: {e}")
            return LLMResponse(
                content=f"[LLM调用失败: {e}]",
                model=self.config.model,
                provider=self.config.name,
                latency_ms=latency,
                metadata={"status": "error", "error": str(e)},
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
        """生成响应"""
        provider = self.get_provider(role)
        return provider.chat(messages, stream=stream)

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
