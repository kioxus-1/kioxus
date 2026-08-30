"""
Kioxus Core v2 — Kioxus核心模块

架构：
  engine.py   — 核心引擎，调度核心循环
  input.py    — 输入处理，意图识别
  context.py  — 上下文组装，记忆+会话+系统提示
  llm.py      — LLM客户端，统一调用接口
  output.py   — 输出处理，响应格式化
  session.py  — 会话管理，对话历史+checkpoint

核心循环：
  输入 → 回忆 → 思考 → 规划 → 行动 → 观察 → 输出 → 反思
"""

from .engine import Engine, get_engine, reset_engine, EngineState
from .input import InputProcessor, ParsedInput
from .context import ContextBuilder, ContextBudget, ContextResult, ContextTracker, ContextBudgetExceeded
from .llm import LLMClient, LLMMessage, LLMResponse, ModelRole, ProviderConfig, get_llm_client, reset_llm_client
from .output import OutputHandler, Observation
from .session import SessionManager, Session, Turn, get_session_manager
from .memory_bridge import MemoryBridge
from .reasoning import ReasoningEngine, ReasoningMode, ReasoningResult, get_reasoning_engine
from .planner import Planner, Plan, PlanStep, Complexity, get_planner
from .tools import ToolRegistry, ToolMeta, ToolResult, ToolCategory, get_tool_registry, reset_tool_registry
from .builtin_tools import register_builtin_tools, http_fetch, file_read, file_write, file_list, code_exec
from .decomposer import GoalDecomposer, DecompositionResult, SubTask, DecomposeStrategy, get_decomposer, reset_decomposer
from .verifier import Verifier, Verdict, VerificationResult, get_verifier, reset_verifier
from .sandbox import Sandbox, SandboxLevel, SandboxPolicy, SandboxResult, get_sandbox, reset_sandbox, sandbox_exec

__version__ = "2.1.0"

__all__ = [
    # 引擎
    "Engine", "get_engine", "reset_engine", "EngineState",
    # 输入
    "InputProcessor", "ParsedInput",
    # 上下文
    "ContextBuilder", "ContextBudget", "ContextResult", "ContextTracker", "ContextBudgetExceeded",
    # LLM
    "LLMClient", "LLMMessage", "LLMResponse", "ModelRole",
    "get_llm_client", "reset_llm_client",
    # 输出
    "OutputHandler", "Observation",
    # 会话
    "SessionManager", "Session", "Turn", "get_session_manager",
    # 工具
    "ToolRegistry", "ToolMeta", "ToolResult", "ToolCategory",
    "get_tool_registry", "reset_tool_registry",
    "register_builtin_tools",
    # 目标分解
    "GoalDecomposer", "DecompositionResult", "SubTask", "DecomposeStrategy",
    "get_decomposer", "reset_decomposer",
    # 验证器
    "Verifier", "Verdict", "VerificationResult", "get_verifier", "reset_verifier",
    # 沙箱
    "Sandbox", "SandboxLevel", "SandboxPolicy", "SandboxResult", "get_sandbox", "reset_sandbox", "sandbox_exec",
]
