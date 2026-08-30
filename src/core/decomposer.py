"""
Kioxus Core v2 — 目标分解器
将复杂目标拆解为可执行的子任务

三种分解策略：
  规则分解 — 基于关键词模式匹配（快速、确定性）
  LLM分解  — 用大模型拆解（灵活、处理复杂目标）
  混合分解 — 先规则尝试，失败则LLM
"""

import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

from .llm import LLMClient, LLMMessage, ModelRole

logger = logging.getLogger(__name__)


class DecomposeStrategy(Enum):
    """DecomposeStrategy"""
    RULE = "rule"      # 规则分解
    LLM = "llm"        # LLM分解
    HYBRID = "hybrid"   # 混合


@dataclass
class SubTask:
    """子任务"""
    task_id: int
    description: str
    tool: Optional[str] = None     # 需要的工具
    depends_on: List[int] = field(default_factory=list)  # 依赖的任务ID
    priority: int = 0              # 优先级（0最高）
    status: str = "pending"        # pending / running / done / failed
    result: Optional[str] = None   # 执行结果


@dataclass
class DecompositionResult:
    """分解结果"""
    original_goal: str
    subtasks: List[SubTask]
    strategy: DecomposeStrategy
    confidence: float              # 0-1
    needs_tools: bool
    tools_used: List[str] = field(default_factory=list)
    reasoning: str = ""            # 分解理由

    @property
    def is_trivial(self) -> bool:
        """是否是简单任务（不需要分解）"""
        return len(self.subtasks) <= 1

    @property
    def next_task(self) -> Optional[SubTask]:
        """获取下一个可执行的子任务"""
        for task in self.subtasks:
            if task.status != "pending":
                continue
            deps_met = all(
                self.subtasks[dep_id - 1].status == "done"
                for dep_id in task.depends_on
                if dep_id <= len(self.subtasks)
            )
            if deps_met:
                return task
        return None

    def mark_done(self, task_id: int, result: str = None):
        """mark_done"""
        for task in self.subtasks:
            if task.task_id == task_id:
                task.status = "done"
                task.result = result
                break

    def mark_failed(self, task_id: int, error: str = None):
        """mark_failed"""
        for task in self.subtasks:
            if task.task_id == task_id:
                task.status = "failed"
                task.result = error
                break

    @property
    def progress(self) -> str:
        """progress"""
        done = sum(1 for t in self.subtasks if t.status == "done")
        total = len(self.subtasks)
        return f"{done}/{total}"

    @property
    def all_done(self) -> bool:
        """all_done"""
        return all(t.status == "done" for t in self.subtasks)


# ============== 工具关键词映射 ==============

TOOL_KEYWORDS = {
    "http_fetch": ["打开网页", "抓取网页", "获取网页", "网页内容", "fetch", "url"],
    "file_read": ["读取文件", "打开文件", "查看文件", "文件内容"],
    "file_write": ["写入文件", "保存文件", "创建文件", "输出到文件"],
    "file_list": ["列出文件", "查看目录", "文件列表", "ls"],
    "code_exec": ["执行代码", "运行代码", "写代码", "写脚本", "python"],
    "web_search": ["搜索", "搜一下", "查找资料", "搜一搜"],
    "weather": ["天气", "气温", "下雨"],
}


def _detect_tools(text: str) -> List[str]:
    """从文本中检测需要的工具"""
    tools = []
    for tool, keywords in TOOL_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                tools.append(tool)
                break
    return tools


# ============== 目标分解器 ==============

class GoalDecomposer:
    """目标分解器"""

    # 分隔符模式（用于规则分解）
    # 先按分隔符拆分，再提取各段内容
    SPLIT_KEYWORDS = [
        "首先", "第一步", "1.", "1、", "1）",
        "然后", "接着", "第二步", "2.", "2、", "2）",
        "最后", "第三步", "3.", "3、", "3）",
        "并且", "同时", "另外", "此外",
    ]

    # 复杂度关键词
    COMPLEX_KEYWORDS = [
        "首先", "然后", "最后", "接着",
        "第一步", "第二步", "第三步", "步骤",
        "并且", "同时", "另外", "此外",
        "分析并", "比较并", "设计并",
    ]

    def __init__(self, llm: LLMClient = None):
        """__init__"""
        self.llm = llm

    def decompose(
        self,
        goal: str,
        context: str = "",
        strategy: DecomposeStrategy = DecomposeStrategy.HYBRID,
    ) -> DecompositionResult:
        """分解目标"""
        # 检测需要的工具
        tools = _detect_tools(goal)

        if strategy == DecomposeStrategy.RULE:
            return self._rule_decompose(goal, tools)
        elif strategy == DecomposeStrategy.LLM:
            return self._llm_decompose(goal, context, tools)
        else:
            # 混合：先规则，失败则LLM
            result = self._rule_decompose(goal, tools)
            if result.confidence < 0.5 and self.llm:
                return self._llm_decompose(goal, context, tools)
            return result

    def _is_complex(self, goal: str) -> bool:
        """判断是否是复杂目标"""
        count = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in goal)
        return count >= 2 or len(goal) > 50

    def _split_by_keywords(self, text: str) -> List[str]:
        """按分隔符关键词拆分文本"""
        # 构建正则：匹配所有分隔符位置
        pattern = "(?:" + "|".join(re.escape(kw) for kw in self.SPLIT_KEYWORDS) + ")"
        splits = list(re.finditer(pattern, text))

        if not splits:
            return []

        parts = []
        for i, match in enumerate(splits):
            start = match.end()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            segment = text[start:end].strip()
            # 去掉段内可能残留的标点前缀
            segment = re.sub(r"^[，,。.、;；\s]+", "", segment)
            if segment:
                parts.append(segment)

        # 如果第一个分隔符不在开头，前面的内容也算一段
        if splits[0].start() > 0:
            prefix = text[:splits[0].start()].strip()
            if prefix:
                parts.insert(0, prefix)

        return parts

    def _rule_decompose(self, goal: str, tools: List[str]) -> DecompositionResult:
        """规则分解 — 基于关键词模式"""
        # 简单任务不分解
        if not self._is_complex(goal):
            return DecompositionResult(
                original_goal=goal,
                subtasks=[SubTask(task_id=1, description=goal, tool=tools[0] if tools else None)],
                strategy=DecomposeStrategy.RULE,
                confidence=1.0,
                needs_tools=len(tools) > 0,
                tools_used=tools,
            )

        # 尝试按分隔符拆分
        parts = self._split_by_keywords(goal)

        # 如果没拆出来，尝试按句号/分号拆
        if not parts:
            parts = [p.strip() for p in re.split(r"[。；;]", goal) if p.strip()]

        # 如果只拆出1个，不算分解成功
        if len(parts) <= 1:
            return DecompositionResult(
                original_goal=goal,
                subtasks=[SubTask(task_id=1, description=goal, tool=tools[0] if tools else None)],
                strategy=DecomposeStrategy.RULE,
                confidence=0.3,
                needs_tools=len(tools) > 0,
                tools_used=tools,
                reasoning="规则分解未能拆分，降级为单任务",
            )

        # 构建子任务
        subtasks = []
        for i, part in enumerate(parts):
            part_tools = _detect_tools(part)
            subtask = SubTask(
                task_id=i + 1,
                description=part,
                tool=part_tools[0] if part_tools else None,
                depends_on=[i] if i > 0 else [],
            )
            subtasks.append(subtask)

        all_tools = list(set(t for st in subtasks for t in _detect_tools(st.description)))
        all_tools.extend([t for t in tools if t not in all_tools])

        return DecompositionResult(
            original_goal=goal,
            subtasks=subtasks,
            strategy=DecomposeStrategy.RULE,
            confidence=0.7,
            needs_tools=len(all_tools) > 0,
            tools_used=all_tools,
            reasoning=f"规则拆分为{len(subtasks)}个子任务",
        )

    def _llm_decompose(
        self,
        goal: str,
        context: str,
        tools: List[str],
    ) -> DecompositionResult:
        """LLM分解 — 用大模型拆解"""
        if not self.llm:
            return self._rule_decompose(goal, tools)

        tools_desc = ", ".join(tools) if tools else "无"

        prompt = f"""请将以下目标分解为可执行的子任务。

目标：{goal}
{f'上下文：{context}' if context else ''}
可用工具：{tools_desc}

请用以下格式输出（每行一个子任务）：
步骤1: [任务描述] [需要的工具名（如需要）]
步骤2: [任务描述] [依赖步骤1]
...

要求：
- 每个步骤应该是独立可执行的
- 如果有依赖关系，标注依赖
- 最多拆为5步"""

        messages = [
            LLMMessage(role="system", content="你是一个任务分解器。将复杂目标拆解为可执行的子任务。"),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            resp = self.llm.generate(messages, role=ModelRole.REASONING)
            subtasks = self._parse_subtasks(resp.content)

            if not subtasks:
                # LLM没返回有效结果，降级
                return self._rule_decompose(goal, tools)

            all_tools = list(set(t for st in subtasks if st.tool for t in [st.tool]))

            return DecompositionResult(
                original_goal=goal,
                subtasks=subtasks,
                strategy=DecomposeStrategy.LLM,
                confidence=0.85,
                needs_tools=len(all_tools) > 0,
                tools_used=all_tools,
                reasoning=f"LLM拆分为{len(subtasks)}个子任务",
            )
        except Exception as e:
            logger.error(f"[Decomposer] LLM分解失败: {e}")
            return self._rule_decompose(goal, tools)

    def _parse_subtasks(self, raw: str) -> List[SubTask]:
        """解析LLM输出的子任务"""
        subtasks = []
        lines = raw.split("\n")

        for line in lines:
            line = line.strip()
            match = re.match(r"步骤(\d+)[：:]\s*(.+)", line)
            if match:
                task_id = int(match.group(1))
                desc = match.group(2)

                # 检测工具
                tool = None
                for t in _detect_tools(desc):
                    tool = t
                    break

                # 检测依赖
                depends = []
                dep_match = re.findall(r"依赖(?:步骤)?(\d+)", desc)
                if dep_match:
                    depends = [int(d) for d in dep_match]

                subtasks.append(SubTask(
                    task_id=task_id,
                    description=desc,
                    tool=tool,
                    depends_on=depends,
                ))

        return subtasks


# ============== 单例 ==============

_instance: Optional[GoalDecomposer] = None


def get_decomposer(llm: LLMClient = None) -> GoalDecomposer:
    """get_decomposer"""
    global _instance
    if _instance is None:
        _instance = GoalDecomposer(llm)
    return _instance


def reset_decomposer():
    """reset_decomposer"""
    global _instance
    _instance = None
