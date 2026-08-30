"""
Kioxus Core v2 — 规划器
任务分解、步骤规划、工具选择

三种复杂度：
  simple  (1-2步)  — 直接执行，不规划
  medium  (3-5步)  — 简单规划，线性执行
  complex (5+步)   — 详细规划，可能有分支
"""

import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .llm import LLMClient, LLMMessage

logger = logging.getLogger(__name__)


class Complexity(Enum):
    """Complexity"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class PlanStep:
    """规划步骤"""
    step_id: int
    action: str                 # 动作描述
    tool: Optional[str] = None  # 需要的工具
    params: Dict = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)  # 依赖的步骤
    status: str = "pending"     # pending / running / done / failed


@dataclass
class Plan:
    """规划结果"""
    goal: str                   # 目标
    steps: List[PlanStep]       # 步骤列表
    complexity: Complexity      # 复杂度
    needs_tool: bool            # 是否需要工具
    tools_used: List[str] = field(default_factory=list)
    fallback: Optional[str] = None  # 备选方案
    metadata: Dict = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        """is_empty"""
        return len(self.steps) == 0

    @property
    def next_step(self) -> Optional[PlanStep]:
        """获取下一个待执行的步骤"""
        for step in self.steps:
            if step.status == "pending":
                # 检查依赖是否完成
                deps_met = all(
                    self.steps[dep_id - 1].status == "done"
                    for dep_id in step.depends_on
                    if dep_id <= len(self.steps)
                )
                if deps_met:
                    return step
        return None

    def mark_done(self, step_id: int):
        """mark_done"""
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "done"
                break

    def mark_failed(self, step_id: int):
        """mark_failed"""
        for step in self.steps:
            if step.step_id == step_id:
                step.status = "failed"
                break


class Planner:
    """规划器"""

    # 工具名 → 触发关键词
    TOOL_KEYWORDS = {
        "weather": ["天气", "温度", "下雨"],
        "search": ["搜索", "查找", "搜一下"],
        "file_read": ["读取", "打开文件", "查看文件"],
        "file_write": ["写入", "保存", "创建文件"],
        "code": ["代码", "编程", "函数", "脚本"],
        "image": ["图片", "图像", "截图"],
    }

    def __init__(self, llm: LLMClient = None):
        """__init__"""
        self.llm = llm
        self._tools: Dict[str, Callable] = {}

    def register_tool(self, name: str, handler: Callable):
        """register_tool"""
        self._tools[name] = handler

    def has_tool(self, name: str) -> bool:
        """has_tool"""
        return name in self._tools

    def plan(
        self,
        goal: str,
        context: str = "",
        available_tools: List[str] = None,
    ) -> Plan:
        """为给定目标生成执行计划"""
        if available_tools is None:
            available_tools = list(self._tools.keys())

        # 1. 判断复杂度
        complexity = self._assess_complexity(goal)

        # 2. 检测需要的工具
        detected_tools = self._detect_tools(goal)

        # 3. 根据复杂度生成计划
        if complexity == Complexity.SIMPLE:
            return self._simple_plan(goal, detected_tools)
        elif complexity == Complexity.MEDIUM:
            return self._medium_plan(goal, context, detected_tools, available_tools)
        else:
            return self._complex_plan(goal, context, detected_tools, available_tools)

    def _assess_complexity(self, goal: str) -> Complexity:
        """评估任务复杂度"""
        # 简单：短消息、问候、单步操作
        if len(goal) < 15:
            return Complexity.SIMPLE

        simple_indicators = ["你好", "谢谢", "好的", "嗯", "是", "不是"]
        for kw in simple_indicators:
            if goal.strip() == kw:
                return Complexity.SIMPLE

        # 复杂：多步骤关键词（优先检查）
        complex_keywords = [
            "首先", "然后", "最后", "第一步", "步骤",
            "设计", "架构", "系统", "方案", "计划",
            "分析并", "比较并", "同时", "并且",
        ]
        complex_count = sum(1 for kw in complex_keywords if kw in goal)
        if complex_count >= 2:
            return Complexity.COMPLEX

        # 中等：需要工具或多步操作
        medium_keywords = ["帮我", "写一个", "创建", "修改", "分析", "总结"]
        for kw in medium_keywords:
            if kw in goal:
                return Complexity.MEDIUM

        return Complexity.SIMPLE

    def _detect_tools(self, goal: str) -> List[str]:
        """检测需要的工具"""
        tools = []
        for tool, keywords in self.TOOL_KEYWORDS.items():
            for kw in keywords:
                if kw in goal:
                    tools.append(tool)
                    break
        return tools

    def _simple_plan(self, goal: str, tools: List[str]) -> Plan:
        """简单计划：直接执行"""
        steps = []
        if tools:
            steps.append(PlanStep(
                step_id=1,
                action=goal,
                tool=tools[0],
                params={"query": goal},
            ))
        else:
            steps.append(PlanStep(
                step_id=1,
                action=goal,
            ))

        return Plan(
            goal=goal,
            steps=steps,
            complexity=Complexity.SIMPLE,
            needs_tool=len(tools) > 0,
            tools_used=tools,
        )

    def _medium_plan(
        self, goal: str, context: str, tools: List[str], available: List[str]
    ) -> Plan:
        """中等计划：线性步骤"""
        # 如果有LLM，用LLM生成计划
        if self.llm:
            return self._llm_plan(goal, context, tools, available, Complexity.MEDIUM)

        # 否则用规则生成
        steps = []
        step_id = 1

        # 如果需要工具，先调工具
        for tool in tools:
            if tool in available:
                steps.append(PlanStep(
                    step_id=step_id,
                    action=f"调用 {tool}",
                    tool=tool,
                    params={"query": goal},
                ))
                step_id += 1

        # 最后生成回复
        steps.append(PlanStep(
            step_id=step_id,
            action="生成回复",
            depends_on=[s.step_id for s in steps],
        ))

        return Plan(
            goal=goal,
            steps=steps,
            complexity=Complexity.MEDIUM,
            needs_tool=len(tools) > 0,
            tools_used=tools,
        )

    def _complex_plan(
        self, goal: str, context: str, tools: List[str], available: List[str]
    ) -> Plan:
        """复杂计划：LLM生成详细步骤"""
        if self.llm:
            return self._llm_plan(goal, context, tools, available, Complexity.COMPLEX)

        # 降级为中等计划，但保持 COMPLEX 标记
        plan = self._medium_plan(goal, context, tools, available)
        plan.complexity = Complexity.COMPLEX
        return plan

    def _llm_plan(
        self,
        goal: str,
        context: str,
        tools: List[str],
        available: List[str],
        complexity: Complexity,
    ) -> Plan:
        """用LLM生成计划"""
        tools_info = ", ".join(available) if available else "无可用工具"

        prompt = f"""请为以下目标制定执行计划。

目标：{goal}
{f'上下文：{context}' if context else ''}
可用工具：{tools_info}

请用以下格式输出（每行一个步骤）：
步骤1: [动作描述] [工具名（如需要）]
步骤2: [动作描述]
..."""

        messages = [
            LLMMessage(role="system", content="你是一个任务规划器。请将目标分解为可执行的步骤。"),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            resp = self.llm.generate(messages)
            steps = self._parse_plan_steps(resp.content)

            return Plan(
                goal=goal,
                steps=steps,
                complexity=complexity,
                needs_tool=any(s.tool for s in steps),
                tools_used=[s.tool for s in steps if s.tool],
            )
        except Exception as e:
            logger.error(f"[Planner] LLM规划失败: {e}")
            return self._medium_plan(goal, context, tools, available)

    def _parse_plan_steps(self, raw: str) -> List[PlanStep]:
        """解析LLM生成的计划"""
        import re
        steps = []
        lines = raw.split("\n")

        for line in lines:
            line = line.strip()
            match = re.match(r"步骤(\d+)[：:]\s*(.+)", line)
            if match:
                step_id = int(match.group(1))
                action = match.group(2)

                # 检查是否指定了工具
                tool = None
                for tool_name in self._tools:
                    if tool_name in action:
                        tool = tool_name
                        break

                steps.append(PlanStep(
                    step_id=step_id,
                    action=action,
                    tool=tool,
                ))

        return steps


# ============== 单例 ==============

_instance: Optional[Planner] = None


def get_planner(llm: LLMClient = None) -> Planner:
    """get_planner"""
    global _instance
    if _instance is None:
        _instance = Planner(llm)
    return _instance
