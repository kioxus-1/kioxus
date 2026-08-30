"""
Provider Registry — 插件化Provider管理

Provider插件架构：
- Provider自注册，不硬编码
- 支持多Key轮换（限流时自动切换）
- 统一的Provider接口
"""

import os
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable


@dataclass
class ProviderConfig:
    """单个Provider配置"""
    name: str
    api_url: str
    api_keys: List[str] = field(default_factory=list)  # 支持多Key
    model: str = ""
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 30
    # 轮换状态
    _current_key_idx: int = field(default=0, repr=False)
    _key_failures: Dict[int, float] = field(default_factory=dict, repr=False)
    _cooldown_seconds: int = 60

    @property
    def api_key(self) -> str:
        """获取当前可用的Key"""
        if not self.api_keys:
            return ""
        return self.api_keys[self._current_key_idx % len(self.api_keys)]

    def rotate_key(self) -> Optional[str]:
        """轮换到下一个Key，返回None表示所有Key都不可用"""
        now = time.time()
        for i in range(len(self.api_keys)):
            idx = (self._current_key_idx + 1 + i) % len(self.api_keys)
            last_fail = self._key_failures.get(idx, 0)
            if now - last_fail > self._cooldown_seconds:
                self._current_key_idx = idx
                return self.api_keys[idx]
        return None

    def mark_key_failed(self):
        """标记当前Key失败（限流触发轮换）"""
        self._key_failures[self._current_key_idx] = time.time()

    def mark_key_success(self):
        """标记当前Key成功（重置失败计数）"""
        self._key_failures.pop(self._current_key_idx, None)


class ProviderRegistry:
    """Provider注册中心"""

    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._default_provider: Optional[str] = None

    def register(self, config: ProviderConfig):
        """注册一个Provider"""
        self._providers[config.name] = config
        if not self._default_provider:
            self._default_provider = config.name

    def unregister(self, name: str):
        """注销一个Provider"""
        self._providers.pop(name, None)
        if self._default_provider == name:
            self._default_provider = next(iter(self._providers), None)

    def get(self, name: Optional[str] = None) -> Optional[ProviderConfig]:
        """获取Provider配置"""
        return self._providers.get(name or self._default_provider)

    def list_providers(self) -> List[str]:
        """列出所有已注册的Provider"""
        return list(self._providers.keys())

    def set_default(self, name: str):
        """设置默认Provider"""
        if name in self._providers:
            self._default_provider = name

    @property
    def default(self) -> Optional[ProviderConfig]:
        return self._providers.get(self._default_provider)

    def load_from_config(self, config_path: str):
        """从config/kioxus.json加载Provider配置"""
        import json
        if not os.path.exists(config_path):
            return

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        for name, pcfg in cfg.get("providers", {}).items():
            # 从环境变量读取Key（支持逗号分隔的多Key）
            env_var = pcfg.get("api_key_env", "")
            raw_key = os.getenv(env_var, "")
            keys = [k.strip() for k in raw_key.split(",") if k.strip()] if raw_key else []

            self.register(ProviderConfig(
                name=name,
                api_url=pcfg.get("api_url", ""),
                api_keys=keys,
                model=pcfg.get("model", ""),
                max_tokens=pcfg.get("max_tokens", 2048),
                temperature=pcfg.get("temperature", 0.7),
            ))

        default = cfg.get("default_provider")
        if default and default in self._providers:
            self._default_provider = default

    def save_to_config(self, config_path: str):
        """保存当前Provider配置到config/kioxus.json"""
        import json
        cfg = {"providers": {}, "default_provider": self._default_provider or ""}
        for name, p in self._providers.items():
            env_var = f"{name.upper()}_API_KEY"
            cfg["providers"][name] = {
                "api_url": p.api_url,
                "api_key_env": env_var,
                "model": p.model,
                "max_tokens": p.max_tokens,
                "temperature": p.temperature,
            }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

    def get_status(self) -> Dict:
        """获取所有Provider状态"""
        result = {}
        for name, p in self._providers.items():
            result[name] = {
                "api_url": p.api_url,
                "model": p.model,
                "key_count": len(p.api_keys),
                "has_key": bool(p.api_keys),
                "is_default": name == self._default_provider,
            }
        return result


# 全局注册中心
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    return _registry
