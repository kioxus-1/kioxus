"""
Kioxus Core v2 — 记忆桥接器
连接 Engine 和 memory 四层记忆系统

职责：
  读：通过 MemoryRouter 注入上下文（已在 ContextBuilder 中完成）
  写：从对话中提取重要信息，存入四层记忆
  反思：定期分析对话模式，提炼经验
"""

import re
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# 延迟导入，避免循环依赖
_save_memory = None


def _get_save_memory():
    """_get_save_memory"""
    global _save_memory
    if _save_memory is None:
        try:
            from memory import save_memory
            _save_memory = save_memory
        except ImportError:
            logger.warning("memory not available")
            _save_memory = lambda **kwargs: {"success": False, "errors": ["memory not available"]}
    return _save_memory


class MemoryBridge:
    """记忆桥接器 — 对话与记忆系统之间的桥梁"""

    # 用户信息关键词（必须是陈述句，排除问句）
    # 排除: 什么 谁 哪 几 怎么 多少 为什么 是否
    _Q = r'[^？?！!。，,什么谁哪几怎么多少为什么是否]{1,10}'
    USER_INFO_PATTERNS = [
        (r"^我叫(" + _Q + r")$", "名字", "用户叫{name}"),
        (r"^我的名字是(" + _Q + r")$", "名字", "用户的名字是{name}"),
        (r"^我是(" + _Q + r")(?:人|的)", "身份", "用户是{name}"),
        (r"^我喜欢([^？?！!。，,什么谁哪几怎么多少为什么是否]{1,20})$", "偏好", "用户喜欢{thing}"),
        (r"^我不喜欢([^？?！!。，,什么谁哪几怎么多少为什么是否]{1,20})$", "偏好", "用户不喜欢{thing}"),
        (r"^我在(" + _Q + r")(?:工作|上学|住)", "位置", "用户在{place}"),
        (r"^我(\d+)岁$", "年龄", "用户{age}岁"),
    ]

    # 知识/学习关键词
    KNOWLEDGE_PATTERNS = [
        (r"(.{2,10})是(.{2,30})", "知识"),
        (r"(.{2,10})的意思是(.{2,30})", "知识"),
        (r"(.{2,10})指的是(.{2,30})", "知识"),
    ]

    def __init__(self, memory_router=None):
        """__init__"""
        self.memory_router = memory_router
        self._turn_count = 0
        self._recent_writes: List[str] = []  # 最近写入的内容，用于去重

    def _is_duplicate(self, content: str, layer: str) -> bool:
        """检查是否与最近写入的内容重复"""
        # 提取核心事实部分（去掉前缀）
        core = content.strip()
        for r in self._recent_writes:
            if r == core:
                return True
        # 也检查文件中是否已有相同内容
        if layer == "core":
            try:
                from pathlib import Path
                core_path = Path(__file__).parent.parent / "memory" / "data" / "core.md"
                if core_path.exists():
                    existing = core_path.read_text(encoding="utf-8")
                    # 提取所有 [事实] 行
                    for line in existing.split("\n"):
                        if line.strip().startswith("[事实]"):
                            fact = line.strip()
                            # 模糊匹配：核心内容相同就视为重复
                            if self._normalize(fact) == self._normalize(core):
                                return True
            except Exception:
                pass
        return False

    @staticmethod
    def _normalize(text: str) -> str:
        """标准化文本用于去重比较"""
        import re
        # 去掉前缀标记和空白
        t = re.sub(r'\[事实\]\s*', '', text)
        t = re.sub(r'\[行动\]\s*', '', t)
        t = t.strip().rstrip('。，,.\n')
        return t

    def save(self, layer: str, content: str, tags: List[str] = None,
             priority: str = "P2", module: str = None) -> dict:
        """写入记忆（自动去重）"""
        # 去重检查
        if self._is_duplicate(content, layer):
            logger.info(f"[Memory] 跳过重复: {content[:50]}")
            return {"success": True, "skipped": "duplicate"}

        save_fn = _get_save_memory()
        try:
            result = save_fn(
                layer=layer,
                content=content,
                tags=tags or [],
                priority=priority,
                module=module,
                source_type="agent",
            )
            if result.get("success"):
                logger.info(f"[Memory] 写入 {layer}: {content[:50]}...")
                # 记录最近写入
                self._recent_writes.append(content.strip())
                if len(self._recent_writes) > 50:
                    self._recent_writes = self._recent_writes[-30:]
            else:
                logger.warning(f"[Memory] 写入失败: {result.get('errors')}")
            return result
        except Exception as e:
            logger.error(f"[Memory] 写入异常: {e}")
            return {"success": False, "errors": [str(e)]}

    def extract_and_save(self, user_msg: str, assistant_reply: str):
        """从对话中提取重要信息并保存"""
        self._turn_count += 1

        # 1. 检测用户个人信息
        for pattern, info_type, template in self.USER_INFO_PATTERNS:
            match = re.search(pattern, user_msg)
            if match:
                groups = match.groups()
                if info_type == "名字":
                    content = f"[事实] {template.format(name=groups[0].strip())}"
                elif info_type == "身份":
                    content = f"[事实] {template.format(name=groups[0].strip())}"
                elif info_type == "偏好":
                    content = f"[事实] {template.format(thing=groups[0].strip())}"
                elif info_type == "位置":
                    content = f"[事实] {template.format(place=groups[0].strip())}"
                elif info_type == "年龄":
                    content = f"[事实] {template.format(age=groups[0])}"
                else:
                    continue

                self.save(
                    layer="core",
                    content=content,
                    tags=["用户信息", info_type],
                    priority="P0",
                )

        # 2. 检测用户纠正（"不是"、"错了"、"不对"）
        correction_patterns = [
            r"不是.{0,5}(?:这个|那个|这样|那样)",
            r"(?:你|这)(?:说|搞|弄)?错了",
            r"不对",
            r"应该是(.{1,20})",
        ]
        for pattern in correction_patterns:
            if re.search(pattern, user_msg):
                self.save(
                    layer="reflection",
                    content=f"[事实] 用户纠正: {user_msg[:100]}",
                    tags=["纠正", "用户反馈"],
                    priority="P1",
                    module="纠正",
                )
                break

        # 3. 每5轮保存一次今日记录
        if self._turn_count % 5 == 0:
            self.save(
                layer="short-term",
                content=f"[记录] 第{self._turn_count}轮对话 | 用户: {user_msg[:50]} | 回复: {assistant_reply[:50]}",
                tags=["对话记录"],
                priority="P3",
            )

    def reflect_session(self, recent_messages: List[Dict]):
        """对最近的对话进行反思"""
        if not recent_messages:
            return

        # 构建对话摘要
        conversation = []
        for msg in recent_messages:
            role = "用户" if msg.get("role") == "user" else "Kioxus"
            content = msg.get("content", "")[:100]
            conversation.append(f"{role}: {content}")

        summary = "\n".join(conversation[-10:])  # 最近10条

        self.save(
            layer="reflection",
            content=f"[事实] 会话反思（第{self._turn_count}轮）:\n{summary}",
            tags=["反思", "会话"],
            priority="P2",
            module="会话反思",
        )

        logger.info(f"[Memory] 会话反思完成，共{len(recent_messages)}条消息")
