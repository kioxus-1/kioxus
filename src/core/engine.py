"""
Kioxus Core v2 — 核心引擎
调度核心循环，串联所有子模块

核心循环：
  输入 → 回忆 → 思考 → 规划 → 行动 → 观察 → 输出 → 反思
"""

import logging
import time
from typing import Dict, Optional, Callable, Any
from pathlib import Path

from .session import SessionManager
from .input import InputProcessor, ParsedInput
from .llm import LLMClient, LLMMessage, get_llm_client
from .context import ContextBuilder, ContextBudget
from .output import OutputHandler, Observation
from .memory_bridge import MemoryBridge
from .reasoning import ReasoningEngine, ReasoningMode, get_reasoning_engine
from .planner import Planner, Plan, get_planner
from .tools import ToolRegistry, ToolResult, get_tool_registry
from .builtin_tools import register_builtin_tools
from .decomposer import GoalDecomposer, DecomposeStrategy, get_decomposer
from .verifier import Verifier, Verdict, get_verifier

logger = logging.getLogger(__name__)


# ============== 引擎状态 ==============

class EngineState:
    """EngineState"""
    IDLE = "idle"
    PROCESSING = "processing"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    OUTPUT = "output"
    REFLECT = "reflect"


# ============== 核心引擎 ==============

class Engine:
    """Kioxus核心引擎"""

    def __init__(
        self,
        config: Dict = None,
        memory_router=None,
        llm_client: LLMClient = None,
        session_manager: SessionManager = None,
        system_prompt: str = None,
    ):
        self.config = config or {}

        # 子模块
        self.input = InputProcessor()
        self.session = session_manager or SessionManager()
        self.llm = llm_client or get_llm_client()

        # ContextBuilder 接记忆模块
        self.context = ContextBuilder(
            system_prompt=system_prompt,
            memory_router=memory_router,
        )

        self.output = OutputHandler()

        # 记忆桥接器
        self.memory = MemoryBridge(memory_router)

        # 推理引擎
        self.reasoning = get_reasoning_engine(self.llm)

        # 规划器
        self.planner = get_planner(self.llm)

        # 工具注册表（使用新的 ToolRegistry）
        self.tool_registry = get_tool_registry()
        # 自动注册内置工具
        if not self.tool_registry.list_tools():
            register_builtin_tools(self.tool_registry)

        # 目标分解器
        self.decomposer = get_decomposer(self.llm)

        # 对抗性验证器
        self.verifier = get_verifier()

        # 状态
        self.state = EngineState.IDLE
        self._turn_count = 0

        # 兼容旧接口的工具注册表
        self._tools: Dict[str, Callable] = {}

    # ========== 工具注册 ==========

    def register_tool(self, name: str, handler: Callable):
        """注册工具（兼容旧接口 + 新 ToolRegistry）"""
        self._tools[name] = handler
        logger.info(f"Registered tool: {name}")

    def call_tool(self, name: str, params: Dict = None) -> Any:
        """调用工具（优先使用 ToolRegistry）"""
        # 先查 ToolRegistry
        if self.tool_registry.has(name):
            result = self.tool_registry.call(name, params)
            if result.success:
                return result.output
            raise RuntimeError(result.error)
        # 兼容旧接口
        if name in self._tools:
            return self._tools[name](**(params or {}))
        raise ValueError(f"Tool '{name}' not registered")

    def has_tool(self, name: str) -> bool:
        """has_tool"""
        return self.tool_registry.has(name) or name in self._tools

    def list_tools(self) -> list:
        """list_tools"""
        return self.tool_registry.list_names() + list(self._tools.keys())

    # ========== 核心循环 ==========

    def process(self, user_message: str) -> str:
        """
        处理一条用户消息，返回响应

        核心循环：
        ① 输入 → ② 回忆 → ③ 思考 → ④ 规划 → ⑤ 行动 → ⑥ 观察 → ⑦ 输出 → ⑧ 反思
        """
        self.state = EngineState.PROCESSING
        start_time = time.time()

        try:
            # ① 输入：解析用户消息
            parsed = self.input.parse(user_message)
            self._log_parsed(parsed)

            # ② 回忆：组装上下文（记忆 + 会话历史 + 系统提示）
            self.state = EngineState.THINKING
            history = self.session.get_recent_messages(10)
            context_result = self.context.build(
                user_message=user_message,
                session_history=history,
                extended=(parsed.urgency == "high" or parsed.intent == "task"),
            )

            # ③ 思考：选择推理模式并执行推理
            self.state = EngineState.THINKING
            reasoning_mode = self.reasoning.select_mode(user_message, parsed.intent)
            reasoning_result = self.reasoning.reason(
                user_message=user_message,
                context=context_result.memory_context,
                mode=reasoning_mode,
                intent=parsed.intent,
            )

            # ④ 规划：生成执行计划
            plan = self.planner.plan(
                goal=user_message,
                context=context_result.memory_context,
                available_tools=self.list_tools(),
            )

            # ⑤ 行动：执行计划
            self.state = EngineState.TOOL_CALL if plan.needs_tool else EngineState.OUTPUT
            observation = self._execute_plan_v2(plan, context_result.messages, parsed, reasoning_result)

            # ⑥ 观察：检查结果
            if observation.is_error:
                self.state = EngineState.ERROR

            # ⑥.5 对抗性验证：独立审查输出
            verification = self.verifier.verify(
                output=observation.content,
                user_input=user_message,
                tool_name=getattr(observation, 'tool_name', None),
                tool_output=getattr(observation, 'tool_output', None),
                is_error=observation.is_error,
            )
            if not verification.passed:
                logger.warning("[Verifier] output failed: %s", verification.error_summary)
                observation.metadata = observation.metadata or {}
                observation.metadata['verification'] = verification.to_dict()
                observation.metadata['verification_failed'] = True

            # ⑦ 输出：格式化响应
            response = self.output.format(observation)

            # ⑧ 反思：决定是否写入记忆
            self._maybe_reflect(parsed, response, observation)

            # 记录会话并自动保存
            self.session.add_turn("user", user_message, {"intent": parsed.intent})
            self.session.add_turn("assistant", response)
            self.session.save_session()

            self._turn_count += 1
            latency = (time.time() - start_time) * 1000
            logger.info(f"[Engine] 处理完成 | 耗时: {latency:.0f}ms | 状态: {self.state}")

            self.state = EngineState.IDLE
            return response

        except Exception as e:
            logger.error(f"[Engine] 处理异常: {e}", exc_info=True)
            self.state = EngineState.ERROR
            error_observation = Observation(
                content=str(e),
                is_error=True,
            )
            # 对异常也做验证（仅记录，不阻塞）
            verification = self.verifier.verify(
                output=str(e),
                user_input=user_message,
                is_error=True,
            )
            error_observation.metadata = error_observation.metadata or {}
            error_observation.metadata["verification"] = verification.to_dict()

            error_response = self.output.format(error_observation)
            # 异常也记录到会话
            self.session.add_turn("user", user_message)
            self.session.add_turn("assistant", error_response)
            self.state = EngineState.IDLE
            return error_response

    def _simple_plan(self, parsed: ParsedInput) -> Dict:
        """
        Phase 1 简单规划
        直接根据意图决定行动
        """
        # 命令类：尝试找匹配的工具
        if parsed.intent == "command":
            for entity in parsed.entities:
                if entity.startswith("tool:"):
                    tool_name = entity.split(":", 1)[1]
                    if self.has_tool(tool_name):
                        return {
                            "type": "tool",
                            "tool": tool_name,
                            "params": {"query": parsed.raw},
                        }
            # 没找到工具，降级为LLM
            return {"type": "llm"}

        # 查询类：LLM + 记忆上下文
        if parsed.intent == "query":
            return {"type": "llm"}

        # 任务类：LLM + 可能需要工具
        if parsed.intent == "task":
            return {"type": "llm"}

        # 聊天类：直接LLM
        return {"type": "llm"}

    def _execute_plan(self, plan: Dict, messages: list, parsed: ParsedInput) -> Observation:
        """执行计划"""
        plan_type = plan.get("type", "llm")

        if plan_type == "tool":
            tool_name = plan.get("tool")
            params = plan.get("params", {})
            try:
                result = self.call_tool(tool_name, params)
                return Observation(
                    content=str(result),
                    is_tool_result=True,
                    tool_name=tool_name,
                    tool_output=result,
                )
            except Exception as e:
                return Observation(
                    content=f"工具调用失败: {e}",
                    is_error=True,
                    tool_name=tool_name,
                )

        # 默认：LLM生成
        try:
            role = self.llm.select_role(parsed.intent)
            response = self.llm.generate(messages, role=role)
            return Observation(
                content=response.content,
                metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "tokens": response.tokens_used,
                    "latency_ms": response.latency_ms,
                },
            )
        except Exception as e:
            return Observation(
                content=f"LLM调用失败: {e}",
                is_error=True,
            )

    def _execute_plan_v2(
        self,
        plan: Plan,
        messages: list,
        parsed: ParsedInput,
        reasoning_result,
    ) -> Observation:
        """执行计划（Phase 2版本）"""
        # 如果推理链断裂，记录警告
        if reasoning_result.chain_broken:
            logger.warning(f"[Engine] 推理链断裂于步骤 {reasoning_result.broken_at}")

        # 遍历计划步骤
        final_content = ""
        for step in plan.steps:
            if step.tool and self.has_tool(step.tool):
                # 调用工具
                try:
                    result = self.call_tool(step.tool, step.params)
                    step.status = "done"
                    final_content = str(result)
                except Exception as e:
                    step.status = "failed"
                    return Observation(
                        content=f"工具调用失败: {e}",
                        is_error=True,
                        tool_name=step.tool,
                    )
            else:
                # LLM 生成
                try:
                    role = self.llm.select_role(parsed.intent)
                    response = self.llm.generate(messages, role=role)
                    step.status = "done"
                    final_content = response.content
                    return Observation(
                        content=final_content,
                        metadata={
                            "model": response.model,
                            "provider": response.provider,
                            "tokens": response.tokens_used,
                            "latency_ms": response.latency_ms,
                            "reasoning_mode": reasoning_result.mode.value,
                            "reasoning_confidence": reasoning_result.confidence,
                        },
                    )
                except Exception as e:
                    step.status = "failed"
                    return Observation(
                        content=f"LLM调用失败: {e}",
                        is_error=True,
                    )

        return Observation(content=final_content or "无输出")

    def _maybe_reflect(self, parsed: ParsedInput, response: str, observation: Observation):
        """反思 — 决定是否写入记忆"""
        user_msg = parsed.raw

        # 1. 错误记录
        if observation.is_error:
            self.memory.save(
                layer="reflection",
                content=f"[事实] 工具调用失败: {observation.content[:200]}",
                tags=["错误", "工具"],
                priority="P1",
                module="错误",
            )

        # 2. 检测用户偏好/事实
        self.memory.extract_and_save(user_msg, response)

        # 3. 每10轮做一次延迟反思
        if self._turn_count > 0 and self._turn_count % 10 == 0:
            recent = self.session.get_recent_messages(10)
            self.memory.reflect_session(recent)

    def _log_parsed(self, parsed: ParsedInput):
        """记录解析结果"""
        logger.info(
            f"[Input] 意图={parsed.intent} | "
            f"实体={parsed.entities[:3]} | "
            f"紧急={parsed.urgency} | "
            f"记忆={parsed.needs_memory} | "
            f"工具={parsed.needs_tools}"
        )

    # ========== 目标分解 ==========

    def decompose_goal(self, goal: str, context: str = "") -> Dict:
        """分解复杂目标为子任务"""
        result = self.decomposer.decompose(goal, context)
        return {
            "goal": result.original_goal,
            "subtasks": [
                {
                    "id": t.task_id,
                    "description": t.description,
                    "tool": t.tool,
                    "depends_on": t.depends_on,
                    "status": t.status,
                }
                for t in result.subtasks
            ],
            "strategy": result.strategy.value,
            "confidence": result.confidence,
            "needs_tools": result.needs_tools,
            "tools": result.tools_used,
        }

    # ========== 状态查询 ==========

    def status(self) -> Dict:
        """引擎状态"""
        return {
            "state": self.state,
            "turn_count": self._turn_count,
            "session_turns": self.session.current.turn_count if self.session.current else 0,
            "tools": self.list_tools(),
            "tool_stats": self.tool_registry.stats(),
        }


# ============== 单例 ==============

_instance: Optional[Engine] = None


def get_engine(
    config: Dict = None,
    memory_router=None,
    llm_client: LLMClient = None,
    system_prompt: str = None,
) -> Engine:
    global _instance
    if _instance is None:
        _instance = Engine(config, memory_router, llm_client, system_prompt=system_prompt)
    return _instance


def reset_engine():
    """重置单例（测试用）"""
    global _instance
    _instance = None
