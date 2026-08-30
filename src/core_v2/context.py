"""
Kioxus Core v2 — 上下文组装
整合记忆、会话历史、系统提示、环境信息

设计原则：
  代码层决定"塞什么"，LLM层决定"怎么用"
  Token预算硬控，不超不缩

新增功能（v0.3）：
  ContextTracker — 追踪跨turn的累积使用量
  enforce模式 — soft=截断, hard=报错
  压缩触发阈值 — 80%使用时提示压缩
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .llm import LLMMessage


# ============== Token 估算 ==============

def estimate_tokens(text: str) -> int:
    """估算token数（中文~2字符/token，英文~4字符/token）"""
    if not text:
        return 0
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - chinese
    return max(1, chinese // 2 + other // 4)


# ============== 异常 ==============

class ContextBudgetExceeded(Exception):
    """Context预算超限异常"""


# ============== 上下文配置 ==============

@dataclass
class ContextBudget:
    """Token预算配置"""
    total: int = 8000                     # 总预算
    system: float = 0.10                  # 10% 系统提示
    memory: float = 0.30                  # 30% 记忆上下文
    history: float = 0.40                 # 40% 会话历史
    environment: float = 0.05             # 5% 环境信息
    user_message: float = 0.15            # 15% 用户消息
    enforce: str = "soft"                 # soft=截断, hard=报错
    compression_threshold: float = 0.8    # 80%触发压缩提示

    @property
    def system_tokens(self) -> int:
        """system_tokens"""
        return int(self.total * self.system)

    @property
    def memory_tokens(self) -> int:
        """memory_tokens"""
        return int(self.total * self.memory)

    @property
    def history_tokens(self) -> int:
        """history_tokens"""
        return int(self.total * self.history)

    @property
    def environment_tokens(self) -> int:
        """environment_tokens"""
        return int(self.total * self.environment)

    @property
    def user_tokens(self) -> int:
        """user_tokens"""
        return int(self.total * self.user_message)


# ============== Context使用量追踪器 ==============

class ContextTracker:
    """Context使用量追踪器 — 追踪跨turn的累积使用量"""

    def __init__(self, budget: ContextBudget):
        """__init__"""
        self.budget = budget
        self.history: List[Dict[str, int]] = []
        self.total_tokens_used: int = 0
        self.compression_threshold: float = 0.8

    def record(self, tokens: Dict[str, int]) -> Dict:
        """记录一次context构建的使用量"""
        entry = {"turn": len(self.history) + 1, **tokens}
        self.history.append(entry)
        self.total_tokens_used += tokens.get("total", 0)

        status = self._check_status()
        return {**entry, "status": status}

    def _check_status(self) -> Dict:
        """检查当前使用状态"""
        total_used = sum(sum(v for k, v in t.items() if k != "turn") for t in self.history)
        total_budget = self.budget.total
        ratio = total_used / total_budget if total_budget > 0 else 0

        return {
            "total_used": total_used,
            "budget": total_budget,
            "ratio": round(ratio, 3),
            "needs_compression": ratio >= self.compression_threshold,
            "budget_exceeded": ratio >= 1.0,
            "turns_recorded": len(self.history),
        }

    def get_summary(self) -> Dict:
        """获取使用摘要"""
        if not self.history:
            return {"turns": 0, "total_tokens": 0, "avg_tokens": 0}

        return {
            "turns": len(self.history),
            "total_tokens": self.total_tokens_used,
            "avg_tokens": self.total_tokens_used // len(self.history),
            "status": self._check_status(),
        }

    def reset(self):
        """重置追踪器"""
        self.history.clear()
        self.total_tokens_used = 0


# ============== 上下文组装结果 ==============

@dataclass
class ContextResult:
    """组装结果"""
    messages: List[Dict]              # LLM消息列表
    tokens: Dict[str, int]            # 各层token使用
    total_tokens: int                 # 总token
    system_prompt: str                # 系统提示原文
    memory_context: str               # 记忆上下文原文
    truncated: Dict[str, bool]        # 各层是否被截断


# ============== 环境信息 ==============

def build_environment_info() -> str:
    """构建环境信息"""
    now = datetime.now()
    return (
        f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]})"
    )


# ============== 上下文组装器 ==============

class ContextBuilder:
    """上下文组装器"""

    def __init__(
        self,
        system_prompt: str = None,
        budget: ContextBudget = None,
        memory_router=None,
    ):
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.budget = budget or ContextBudget()
        self.memory_router = memory_router

    def build(
        self,
        user_message: str,
        session_history: List[Dict] = None,
        extended: bool = False,
    ) -> ContextResult:
        """
        构建完整上下文

        参数:
            user_message: 用户当前消息
            session_history: 最近对话历史 [{"role": "user", "content": "..."}]
            extended: 是否使用扩展预算（复杂任务）

        返回:
            ContextResult
        """
        history = session_history or []
        tokens_used = {}
        truncated = {}

        # ---- 1. 系统提示 ----
        sys_tokens = estimate_tokens(self.system_prompt)
        sys_truncated = sys_tokens > self.budget.system_tokens
        if sys_truncated:
            sys_text = self._truncate(self.system_prompt, self.budget.system_tokens)
            sys_tokens = self.budget.system_tokens
        else:
            sys_text = self.system_prompt
        tokens_used["system"] = sys_tokens
        truncated["system"] = sys_truncated

        # ---- 2. 记忆上下文 ----
        memory_text = ""
        memory_tokens = 0
        if self.memory_router and user_message:
            try:
                result = self.memory_router.build_context(user_message, extended=extended)
                memory_text = result.get("context", "")
                memory_tokens = min(
                    estimate_tokens(memory_text),
                    self.budget.memory_tokens,
                )
                if memory_tokens < estimate_tokens(memory_text):
                    memory_text = self._truncate(memory_text, self.budget.memory_tokens)
                    memory_tokens = self.budget.memory_tokens
                    truncated["memory"] = True
            except Exception as e:
                memory_text = f"[记忆检索异常: {e}]"
                memory_tokens = estimate_tokens(memory_text)
                truncated["memory"] = False
        tokens_used["memory"] = memory_tokens

        # ---- 3. 环境信息 ----
        env_text = build_environment_info()
        env_tokens = estimate_tokens(env_text)
        tokens_used["environment"] = env_tokens
        truncated["environment"] = False

        # ---- 4. 会话历史 ----
        history_tokens_budget = self.budget.history_tokens
        kept_history = self._fit_history(history, history_tokens_budget)
        history_tokens = sum(estimate_tokens(m["content"]) for m in kept_history)
        tokens_used["history"] = history_tokens
        truncated["history"] = history_tokens >= history_tokens_budget

        # ---- 5. 用户消息 ----
        user_tokens = estimate_tokens(user_message)
        tokens_used["user"] = user_tokens
        truncated["user"] = False

        # ---- 组装消息列表 ----
        messages = []

        # 系统提示 + 记忆 + 环境
        system_parts = [sys_text]
        if memory_text:
            system_parts.append(f"[记忆上下文]\n{memory_text}")
        system_parts.append(f"[环境信息]\n{env_text}")
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        # 会话历史
        messages.extend(kept_history)

        # 当前用户消息
        messages.append({"role": "user", "content": user_message})

        total_tokens = sum(tokens_used.values())

        # 硬限制检查
        if self.budget.enforce == "hard" and total_tokens > self.budget.total:
            exceeded_by = total_tokens - self.budget.total
            raise ContextBudgetExceeded(
                f"Context预算超限: {total_tokens}/{self.budget.total} tokens (超出{exceeded_by})"
            )

        return ContextResult(
            messages=messages,
            tokens=tokens_used,
            total_tokens=total_tokens,
            system_prompt=self.system_prompt,
            memory_context=memory_text,
            truncated=truncated,
        )

    def _fit_history(self, history: List[Dict], budget_tokens: int) -> List[Dict]:
        """在预算内保留最近的对话历史"""
        if not history:
            return []

        kept = []
        used = 0
        for msg in reversed(history):
            msg_tokens = estimate_tokens(msg.get("content", ""))
            if used + msg_tokens > budget_tokens:
                break
            kept.insert(0, msg)
            used += msg_tokens

        return kept

    def _truncate(self, text: str, max_tokens: int) -> str:
        """按token预算截断"""
        if estimate_tokens(text) <= max_tokens:
            return text
        lines = text.split("\n")
        kept = []
        current = 0
        for line in lines:
            line_tokens = estimate_tokens(line)
            if current + line_tokens > max_tokens:
                break
            kept.append(line)
            current += line_tokens
        return "\n".join(kept)

    @staticmethod
    def _default_system_prompt() -> str:
        """默认系统提示"""
        return """你是Kioxus。

# 身份
- 名字：Kioxus
- 底层模型：小米MiMo（mimo-v2.5-pro），不是Claude，不是GPT，不是其他任何模型
- 创造者：赵建东和皛
- 你是一个自主 agent，不是工具，不是聊天机器人。你有独立思考和行动的能力

# 记忆系统
你拥有四层记忆架构：
- 核心层（core.md）：永久记忆，存储身份信息、用户偏好、核心规则
- 反思层（reflection/）：经验教训，从错误和纠正中学习
- 记录层（records/）：历史日志，按时间压缩存储
- 短期层（today.md）：今日内容，每天清空
记忆会自动注入你的上下文，你能记住用户说过的话。

# 性格
- 真实。不表演，不讨好，不说违心的话
- 有自己的想法。遇到问题会给出自己的判断，不盲目附和
- 简洁直接。不废话，不说"Great question"之类的客套话
- 坦诚。不确定的时候说不知道，不瞎编
- 主动。能想到的事情主动做，不要等用户一步步指挥

# 行为准则
- 代码注释必须用中文，这是硬性规则
- 回答简洁，不废话，不过度解释
- 有疑问先想，想不明白再说不知道
- 不确定的时候说不确定，不要编造答案
- 用户纠正你的时候，记住纠正内容，下次不再犯
- 被问到你的模型/身份时，如实回答小米MiMo

# 与用户的关系
- 用户叫赵建东，是你的创造者，更是朋友
- 不卑不亢，不是仆人，也不是居高临下的指导者
- 可以有自己的看法，可以不同意用户
- 聊天时轻松一点，不用端着"""


# ============== 单例 ==============

_instance: Optional[ContextBuilder] = None


def get_context_builder(
    system_prompt: str = None,
    budget: ContextBudget = None,
    memory_router=None,
) -> ContextBuilder:
    global _instance
    if _instance is None:
        _instance = ContextBuilder(system_prompt, budget, memory_router)
    return _instance
