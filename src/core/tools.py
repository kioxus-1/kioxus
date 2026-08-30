"""
Kioxus Core v2 — 工具框架
统一工具注册、调用、权限管理

工具类型：
  builtin  — 内置工具（http_fetch, file_read 等）
  custom   — 用户自定义工具
  agent    — agent委托工具
"""

import logging
import time
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """工具分类"""
    WEB = "web"          # 网络相关
    FILE = "file"        # 文件操作
    CODE = "code"        # 代码执行
    AGENT = "agent"      # agent委托
    MEMORY = "memory"    # 记忆操作
    CUSTOM = "custom"    # 自定义


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any               # 输出内容
    error: Optional[str] = None
    latency_ms: float = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class ToolMeta:
    """工具元数据"""
    name: str                 # 工具名（唯一标识）
    description: str          # 工具描述（LLM可见）
    category: ToolCategory    # 分类
    params: Dict = field(default_factory=dict)   # 参数schema
    requires_auth: bool = False
    timeout: int = 30         # 超时秒数
    enabled: bool = True


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        """__init__"""
        self._meta: Dict[str, ToolMeta] = {}
        self._handlers: Dict[str, Callable] = {}
        self._call_count: Dict[str, int] = {}
        self._total_latency: Dict[str, float] = {}

    def register(self, meta: ToolMeta, handler: Callable):
        """注册工具"""
        self._meta[meta.name] = meta
        self._handlers[meta.name] = handler
        self._call_count[meta.name] = 0
        self._total_latency[meta.name] = 0
        logger.info(f"[Tools] 注册: {meta.name} ({meta.category.value})")

    def unregister(self, name: str):
        """注销工具"""
        self._meta.pop(name, None)
        self._handlers.pop(name, None)
        self._call_count.pop(name, None)
        self._total_latency.pop(name, None)

    def has(self, name: str) -> bool:
        """has"""
        return name in self._handlers and self._meta.get(name, ToolMeta("", "", ToolCategory.CUSTOM)).enabled

    def get(self, name: str) -> Optional[ToolMeta]:
        """get"""
        return self._meta.get(name)

    def list_tools(self, category: ToolCategory = None) -> List[ToolMeta]:
        """列出所有工具"""
        tools = [m for m in self._meta.values() if m.enabled]
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def list_names(self) -> List[str]:
        """list_names"""
        return [name for name, meta in self._meta.items() if meta.enabled]

    def describe_for_llm(self) -> str:
        """生成LLM可读的工具描述"""
        tools = self.list_tools()
        if not tools:
            return "无可用工具"

        lines = ["可用工具："]
        for t in tools:
            params_str = ", ".join(f"{k}: {v}" for k, v in t.params.items()) if t.params else "无参数"
            lines.append(f"- {t.name}: {t.description} (参数: {params_str})")
        return "\n".join(lines)

    def call(self, name: str, params: Dict = None) -> ToolResult:
        """调用工具"""
        if name not in self._handlers:
            return ToolResult(success=False, output=None, error=f"工具 '{name}' 未注册")

        meta = self._meta.get(name)
        if meta and not meta.enabled:
            return ToolResult(success=False, output=None, error=f"工具 '{name}' 已禁用")

        start = time.time()
        try:
            result = self._handlers[name](**(params or {}))
            latency = (time.time() - start) * 1000

            self._call_count[name] = self._call_count.get(name, 0) + 1
            self._total_latency[name] = self._total_latency.get(name, 0) + latency

            if isinstance(result, ToolResult):
                result.latency_ms = latency
                return result

            return ToolResult(
                success=True,
                output=result,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.error(f"[Tools] {name} 调用失败: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                latency_ms=latency,
            )

    def stats(self) -> Dict:
        """工具调用统计"""
        stats = {}
        for name in self._meta:
            count = self._call_count.get(name, 0)
            total = self._total_latency.get(name, 0)
            stats[name] = {
                "calls": count,
                "avg_latency_ms": round(total / max(count, 1), 1),
                "total_latency_ms": round(total, 1),
            }
        return stats


# ============== 单例 ==============

_instance: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """get_tool_registry"""
    global _instance
    if _instance is None:
        _instance = ToolRegistry()
    return _instance


def reset_tool_registry():
    """reset_tool_registry"""
    global _instance
    _instance = None
