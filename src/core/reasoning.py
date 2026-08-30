"""
Kioxus Core v2 — 推理引擎
链式思考、推理监控、置信度评估

三种推理模式：
  直接响应 — 不推理，直接回答（问候、简单对话）
  链式思考 — 一步一步推理（复杂问题、分析）
  反思推理 — 推理 + 自我验证（关键决策、高风险操作）
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

from .llm import LLMClient, LLMMessage, ModelRole

logger = logging.getLogger(__name__)


class ReasoningMode(Enum):
    """ReasoningMode"""
    DIRECT = "direct"          # 直接响应
    CHAIN = "chain"            # 链式思考
    REFLECTIVE = "reflective"  # 反思推理


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_id: int
    content: str               # 思考内容
    step_type: str             # premise / inference / conclusion / verification
    confidence: float          # 0-1 置信度
    source_ids: List[int] = field(default_factory=list)  # 依赖的前置步骤


@dataclass
class ReasoningResult:
    """推理结果"""
    mode: ReasoningMode
    steps: List[ReasoningStep]
    conclusion: str            # 最终结论
    confidence: float          # 整体置信度
    chain_broken: bool         # 推理链是否断裂
    broken_at: Optional[int] = None  # 断裂的步骤ID
    metadata: Dict = field(default_factory=dict)


class ReasoningEngine:
    """推理引擎"""

    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.5

    # 复杂度关键词
    COMPLEX_KEYWORDS = [
        "分析", "比较", "评估", "推理", "论证", "为什么", "原因",
        "利弊", "优缺点", "权衡", "取舍", "策略", "方案",
        "设计", "架构", "规划", "解决",
    ]

    SIMPLE_KEYWORDS = [
        "你好", "hi", "hello", "谢谢", "好的", "嗯", "是的",
        "再见", "晚安", "早上好",
    ]

    def __init__(self, llm: LLMClient = None):
        """__init__"""
        self.llm = llm

    def select_mode(self, user_message: str, intent: str = "chat") -> ReasoningMode:
        """根据输入选择推理模式"""
        # 简单对话 → 直接响应
        for kw in self.SIMPLE_KEYWORDS:
            if kw in user_message.lower():
                return ReasoningMode.DIRECT

        # 短消息 → 直接响应
        if len(user_message) < 10:
            return ReasoningMode.DIRECT

        # 复杂任务 → 反思推理
        if intent == "task":
            return ReasoningMode.REFLECTIVE

        # 包含复杂度关键词 → 链式思考
        for kw in self.COMPLEX_KEYWORDS:
            if kw in user_message:
                return ReasoningMode.CHAIN

        # 查询 → 链式思考
        if intent == "query":
            return ReasoningMode.CHAIN

        # 默认直接响应
        return ReasoningMode.DIRECT

    def reason(
        self,
        user_message: str,
        context: str = "",
        mode: ReasoningMode = None,
        intent: str = "chat",
    ) -> ReasoningResult:
        """执行推理"""
        if mode is None:
            mode = self.select_mode(user_message, intent)

        if mode == ReasoningMode.DIRECT:
            return self._direct_reason(user_message, context)
        elif mode == ReasoningMode.CHAIN:
            return self._chain_reason(user_message, context)
        elif mode == ReasoningMode.REFLECTIVE:
            return self._reflective_reason(user_message, context)
        else:
            return self._direct_reason(user_message, context)

    def _direct_reason(self, message: str, context: str) -> ReasoningResult:
        """直接响应 — 不推理"""
        return ReasoningResult(
            mode=ReasoningMode.DIRECT,
            steps=[],
            conclusion="",
            confidence=1.0,
            chain_broken=False,
        )

    def _chain_reason(self, message: str, context: str) -> ReasoningResult:
        """链式思考 — LLM生成推理链"""
        if not self.llm:
            return self._direct_reason(message, context)

        prompt = f"""请对以下问题进行分步推理。每一步用以下格式：

步骤1: [前提/观察]
步骤2: [推理/分析]
步骤3: [结论]

问题：{message}

{f'上下文：{context}' if context else ''}

请用简洁的中文进行推理，最多5步。"""

        messages = [
            LLMMessage(role="system", content="你是一个善于推理的助手。请分步思考，每步给出置信度（0-1）。"),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            resp = self.llm.generate(messages, role=ModelRole.REASONING)
            raw = resp.content

            # 解析推理步骤
            steps = self._parse_steps(raw)
            overall_confidence = self._calc_overall_confidence(steps)

            # 检查推理链是否断裂
            chain_broken = False
            broken_at = None
            for step in steps:
                if step.confidence < self.CONFIDENCE_THRESHOLD:
                    chain_broken = True
                    broken_at = step.step_id
                    break

            return ReasoningResult(
                mode=ReasoningMode.CHAIN,
                steps=steps,
                conclusion=raw,
                confidence=overall_confidence,
                chain_broken=chain_broken,
                broken_at=broken_at,
            )
        except Exception as e:
            logger.error(f"[Reasoning] 链式思考失败: {e}")
            return self._direct_reason(message, context)

    def _reflective_reason(self, message: str, context: str) -> ReasoningResult:
        """反思推理 — 推理 + 自我验证"""
        if not self.llm:
            return self._direct_reason(message, context)

        prompt = f"""请对以下问题进行推理，并自我验证。

问题：{message}

{f'上下文：{context}' if context else ''}

格式：
推理：[你的推理过程]
验证：[检查推理是否有漏洞，是否有遗漏]
结论：[最终结论]
置信度：[0-1]"""

        messages = [
            LLMMessage(role="system", content="你是一个善于深度推理的助手。推理后请自我验证，检查是否有逻辑漏洞。"),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            resp = self.llm.generate(messages, role=ModelRole.REASONING)
            raw = resp.content

            # 解析
            steps = self._parse_steps(raw)
            overall_confidence = self._calc_overall_confidence(steps)

            chain_broken = False
            broken_at = None
            for step in steps:
                if step.confidence < self.CONFIDENCE_THRESHOLD:
                    chain_broken = True
                    broken_at = step.step_id
                    break

            return ReasoningResult(
                mode=ReasoningMode.REFLECTIVE,
                steps=steps,
                conclusion=raw,
                confidence=overall_confidence,
                chain_broken=chain_broken,
                broken_at=broken_at,
            )
        except Exception as e:
            logger.error(f"[Reasoning] 反思推理失败: {e}")
            return self._direct_reason(message, context)

    def _parse_steps(self, raw: str) -> List[ReasoningStep]:
        """从LLM输出中解析推理步骤"""
        import re
        steps = []
        lines = raw.split("\n")
        step_id = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 匹配 "步骤N:" 或 "推理:" "验证:" "结论:"
            step_match = re.match(r"步骤(\d+)[：:]\s*(.+)", line)
            type_match = re.match(r"(推理|验证|结论|前提|分析)[：:]\s*(.+)", line)

            if step_match:
                step_id += 1
                content = step_match.group(2)
                steps.append(ReasoningStep(
                    step_id=step_id,
                    content=content,
                    step_type="inference",
                    confidence=0.7,  # 默认置信度
                ))
            elif type_match:
                step_id += 1
                type_name = type_match.group(1)
                content = type_match.group(2)
                step_type = {
                    "前提": "premise",
                    "推理": "inference",
                    "分析": "inference",
                    "验证": "verification",
                    "结论": "conclusion",
                }.get(type_name, "inference")

                # 尝试从内容中提取置信度
                confidence = self._extract_confidence(content)

                steps.append(ReasoningStep(
                    step_id=step_id,
                    content=content,
                    step_type=step_type,
                    confidence=confidence,
                ))

        return steps

    @staticmethod
    def _extract_confidence(text: str) -> float:
        """从文本中提取置信度"""
        import re
        match = re.search(r"置信度[：:]\s*([\d.]+)", text)
        if match:
            try:
                return min(1.0, max(0.0, float(match.group(1))))
            except ValueError:
                pass
        return 0.7  # 默认

    @staticmethod
    def _calc_overall_confidence(steps: List[ReasoningStep]) -> float:
        """计算整体置信度（所有步骤的乘积）"""
        if not steps:
            return 1.0
        result = 1.0
        for step in steps:
            result *= step.confidence
        return round(result, 3)


# ============== 单例 ==============

_instance: Optional[ReasoningEngine] = None


def get_reasoning_engine(llm: LLMClient = None) -> ReasoningEngine:
    """get_reasoning_engine"""
    global _instance
    if _instance is None:
        _instance = ReasoningEngine(llm)
    return _instance
