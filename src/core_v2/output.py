"""
Kioxus Core v2 — 输出处理
响应格式化、工具结果处理、错误处理

Phase 1: 基础格式化
Phase 2: 流式输出、多格式
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Observation:
    """观察结果（来自reasoning/engine）"""
    content: str                                # 响应内容
    is_tool_result: bool = False                # 是否是工具调用结果
    is_error: bool = False                      # 是否是错误
    tool_name: Optional[str] = None             # 工具名（如果is_tool_result）
    tool_output: Optional[Any] = None           # 工具原始输出
    metadata: Dict = None                       # 附加信息

    def __post_init__(self):
        """__post_init__"""
        if self.metadata is None:
            self.metadata = {}


class OutputHandler:
    """输出处理器"""

    def format(self, observation: Observation) -> str:
        """格式化最终响应"""
        if observation.is_error:
            return self._format_error(observation)
        elif observation.is_tool_result:
            return self._format_tool_result(observation)
        else:
            return self._format_normal(observation)

    def _format_normal(self, obs: Observation) -> str:
        """格式化普通回复"""
        return obs.content

    def _format_tool_result(self, obs: Observation) -> str:
        """格式化工具执行结果"""
        tool = obs.tool_name or "未知工具"
        output = obs.tool_output or ""

        # 如果输出已经是字符串且合理，直接返回
        if isinstance(output, str):
            content = output
        elif isinstance(output, dict):
            content = str(output)
        elif isinstance(output, list):
            content = "\n".join(str(item) for item in output)
        else:
            content = str(output)

        # 如果content本身已经包含完整信息，直接返回
        if obs.content and len(obs.content) > len(content) * 0.5:
            return obs.content

        return content if content else f"[{tool}] 执行完成，无输出"

    def _format_error(self, obs: Observation) -> str:
        """格式化错误信息"""
        error_msg = obs.content or "未知错误"
        tool = obs.tool_name

        if tool:
            return f"[Error] [{tool}] {error_msg}"
        return f"[Error] {error_msg}"

    def format_stream_chunk(self, text: str) -> str:
        """格式化流式输出片段（Phase 2用）"""
        return text


# ============== 单例 ==============

_instance: Optional[OutputHandler] = None


def get_output_handler() -> OutputHandler:
    """get_output_handler"""
    global _instance
    if _instance is None:
        _instance = OutputHandler()
    return _instance
