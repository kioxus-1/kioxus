"""
Kioxus Core v2 — 输入处理
消息接收、格式解析、意图识别

Phase 1: 规则匹配
Phase 2: 小模型意图识别
"""

import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field


@dataclass
class ParsedInput:
    """解析后的输入"""
    raw: str                    # 原始消息
    intent: str                 # 意图：chat / task / query / command
    entities: List[str]         # 提取的实体
    urgency: str                # 紧急度：low / normal / high
    needs_memory: bool          # 是否需要检索记忆
    needs_tools: bool           # 是否需要工具
    metadata: Dict = field(default_factory=dict)


# ========== 意图关键词 ==========

# 命令类（直接执行）
COMMAND_PATTERNS = [
    r"^(写|创建|新建|生成|删除|移动|重命名|打开|关闭|保存|发送|运行|执行)",
    r"^(帮我|替我|给我)(写|创建|删除|发送|运行|做)",
    r"^(把|将|用).+(改成|改为|转换|翻译|重写)",
]

# 查询类（需要检索）
QUERY_PATTERNS = [
    r"(什么是|怎么|如何|为什么|解释|介绍|告诉我)",
    r"(查|搜索|找|看一下|看看|查一下|帮我查)",
    r"(之前|上次|以前|记得|有没有).*(说过|聊过|提到|做过)",
]

# 任务类（需要规划和工具）
TASK_PATTERNS = [
    r"(帮我|替我).+(查|搜索|找|做|搞|弄|写|创建|发|下|安装|配置)",
    r"(分析|研究|对比|总结|整理|归纳|评估)",
    r"(设计|开发|实现|部署|测试|调试|修复|优化)",
]

# 紧急度关键词
URGENCY_HIGH = {"紧急", "马上", "立刻", "立即", "赶紧", "急", "快", "尽快", "现在就要"}
URGENCY_LOW = {"有空", "不急", "方便的时候", "有时间", "以后", "回头", "慢慢"}

# 工具关键词（提示可能需要工具）
TOOL_HINTS = {
    "天气": "weather",
    "文件": "file",
    "代码": "code",
    "搜索": "search",
    "网页": "web",
    "图片": "image",
    "视频": "video",
    "音频": "audio",
}


class InputProcessor:
    """输入处理器"""

    def __init__(self):
        """__init__"""
        # 预编译正则
        self._command_re = [re.compile(p) for p in COMMAND_PATTERNS]
        self._query_re = [re.compile(p) for p in QUERY_PATTERNS]
        self._task_re = [re.compile(p) for p in TASK_PATTERNS]

    def parse(self, raw: str) -> ParsedInput:
        """解析用户输入"""
        text = raw.strip()
        if not text:
            return ParsedInput(
                raw=raw, intent="chat", entities=[],
                urgency="low", needs_memory=False, needs_tools=False,
            )

        # 1. 意图识别
        intent = self._detect_intent(text)

        # 2. 实体提取
        entities = self._extract_entities(text)

        # 3. 紧急度判断
        urgency = self._detect_urgency(text)

        # 4. 是否需要记忆
        needs_memory = self._needs_memory(text, intent)

        # 5. 是否需要工具
        needs_tools = self._needs_tools(text, intent, entities)

        return ParsedInput(
            raw=raw,
            intent=intent,
            entities=entities,
            urgency=urgency,
            needs_memory=needs_memory,
            needs_tools=needs_tools,
            metadata={"length": len(text), "has_code": self._has_code(text)},
        )

    def _detect_intent(self, text: str) -> str:
        """识别意图"""
        # 优先级：command > task > query > chat

        for pattern in self._command_re:
            if pattern.search(text):
                return "command"

        for pattern in self._task_re:
            if pattern.search(text):
                return "task"

        for pattern in self._query_re:
            if pattern.search(text):
                return "query"

        # 短消息默认为聊天
        if len(text) < 5:
            return "chat"

        return "chat"

    def _extract_entities(self, text: str) -> List[str]:
        """提取实体（简化版）"""
        entities = []

        # 文件路径
        paths = re.findall(r'[A-Za-z]:\\[^\s]+|/[^\s]+\.\w+', text)
        entities.extend(paths)

        # URL
        urls = re.findall(r'https?://[^\s]+', text)
        entities.extend(urls)

        # 引号内容
        quoted = re.findall(r'[""\'](.*?)[""\']', text)
        entities.extend(quoted)

        # 工具提示
        for hint in TOOL_HINTS:
            if hint in text:
                entities.append(f"tool:{TOOL_HINTS[hint]}")

        return entities

    def _detect_urgency(self, text: str) -> str:
        """判断紧急度"""
        for word in URGENCY_HIGH:
            if word in text:
                return "high"
        for word in URGENCY_LOW:
            if word in text:
                return "low"
        return "normal"

    def _needs_memory(self, text: str, intent: str) -> bool:
        """判断是否需要检索记忆"""
        # 查询类和任务类通常需要记忆
        if intent in ("query", "task"):
            return True

        # 包含记忆相关关键词
        memory_hints = ["之前", "上次", "以前", "记得", "说过", "聊过", "提到"]
        for hint in memory_hints:
            if hint in text:
                return True

        return False

    def _needs_tools(self, text: str, intent: str, entities: List[str]) -> bool:
        """判断是否需要工具"""
        # 命令类通常需要工具
        if intent == "command":
            return True

        # 有工具提示实体
        if any(e.startswith("tool:") for e in entities):
            return True

        # 包含文件路径或URL
        if any(e.startswith(("http", "/", "C:\\")) for e in entities):
            return True

        return False

    def _has_code(self, text: str) -> bool:
        """检测是否包含代码"""
        code_indicators = ["```", "def ", "class ", "import ", "function ", "const ", "let ", "var "]
        return any(indicator in text for indicator in code_indicators)
