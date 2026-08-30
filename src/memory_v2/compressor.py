"""
Kioxus Memory System v2 — LLM 压缩操作
Flush Agent、旬记压缩、反思压缩
代码管逻辑，LLM管语义
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Callable
from datetime import datetime

from .memory import MemoryStore, MemoryEntry, parse_frontmatter, build_frontmatter, get_memory_store
from .janitor import validate_flush_output, get_janitor

# ============== Prompt 模板 ==============

FLUSH_PROMPT = """你是一个记忆整理助手。请阅读以下今日对话记录，提取出关键信息。

要求：
1. 只提取会改变未来行为的信息
2. 按优先级分类：P0（必须记住）、P1（应该记住）、P2（可以记住）
3. 每条信息必须包含 [事实] 和 [行动]，标签从标准标签中选择
4. 没有关键信息就输出空数组

标准标签库：{available_tags}

今日记录：
{today_content}

请严格按以下JSON格式输出，不要添加任何其他内容：
```json
{{
  "date": "{date}",
  "priority_summary": {{
    "P0": [{{"fact": "...", "action": "...", "tags": ["..."]}}],
    "P1": [{{"fact": "...", "action": "...", "tags": ["..."]}}],
    "P2": [{{"fact": "...", "action": "...", "tags": ["..."]}}]
  }},
  "unfinished_tasks": ["..."],
  "atmosphere": "..."
}}
```"""

COMPRESS_PROMPT = """你是一个记忆压缩助手。请将以下记忆内容压缩为更精简的版本。

压缩规则：
1. 只留结论，不留过程
2. 只留决定，不留讨论
3. 所有 [行动] 字段必须保留
4. 所有 P0/P1 优先级的记忆必须保留
5. 标签覆盖率必须 > 90%
6. 压缩后的内容必须能独立理解

原始内容：
{original_content}

请输出压缩后的Markdown内容（保留Frontmatter）："""

REFLECTION_COMPRESS_PROMPT = """你是一个反思压缩助手。请将以下反思内容压缩为 SOP（标准操作流程）。

要求：
1. 将具体案例抽象为通用规则
2. 保留所有 [行动] 字段
3. 输出不超过 20 行
4. 用简洁的条目格式

原始反思：
{original_content}

请输出压缩后的SOP（保留Frontmatter）："""

PERIOD_COMPRESS_PROMPT = """你是一个记忆压缩助手。请将以下{period_type}内容压缩为精简版本。

压缩规则：
1. 只留结论，不留过程
2. 只留决定，不留讨论
3. 高分记忆（被多次检索、用户强调过的）优先保留
4. 低分记忆可以精简或删除
5. 保留所有 P0/P1 记忆
6. 标签覆盖率 > 90%

原始内容：
{original_content}

记忆评分（从高到低）：
{scored_entries}

请输出压缩后的Markdown内容（保留Frontmatter）："""


# ============== LLM 调用接口 ==============

# LLM 调用函数类型：接收 messages 列表，返回响应字符串
LLMCallFunc = Callable[[List[Dict], str], str]  # (messages, model) -> response


def default_llm_call(messages: List[Dict], model: str = "default") -> str:
    """
    默认LLM调用 — 使用 core_v2 的 LLMClient
    如果不可用，返回None
    """
    try:
        from core_v2 import get_llm_client, LLMMessage
        client = get_llm_client()
        llm_messages = [LLMMessage(role=m.get('role', 'user'), content=m.get('content', '')) for m in messages]
        response = client.chat(llm_messages)
        if response.success:
            return response.content
    except Exception:
        pass
    return None


# ============== Flush Agent ==============

class FlushAgent:
    """
    Flush Agent — 从 today.md 提取 P0-P2 关键信息
    用小模型执行，输出结构化 JSON
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        llm_call: Optional[LLMCallFunc] = None,
    ):
        self.store = store or get_memory_store()
        self.llm_call = llm_call or default_llm_call

    def run(self, available_tags: List[str] = None) -> Dict:
        """
        执行 Flush
        返回: {"success": bool, "data": dict, "errors": list}
        """
        today_content = self.store.read_today()
        if not today_content.strip():
            return {"success": True, "data": None, "errors": [], "message": "today.md is empty"}

        date_str = datetime.now().strftime("%Y-%m-%d")
        tags_str = ", ".join(available_tags[:50]) if available_tags else "通用, 错误, 认知, 学习, 用户偏好"

        prompt = FLUSH_PROMPT.format(
            available_tags=tags_str,
            today_content=today_content,
            date=date_str,
        )

        messages = [
            {"role": "system", "content": "你是一个记忆整理助手，严格按JSON格式输出。"},
            {"role": "user", "content": prompt},
        ]

        # 调用LLM
        response = self.llm_call(messages, "small")
        if not response:
            return {"success": False, "data": None, "errors": ["LLM call failed"]}

        # 解析JSON
        try:
            data = self._extract_json(response)
            valid, errors = validate_flush_output(data)
            if valid:
                return {"success": True, "data": data, "errors": []}
            else:
                return {"success": False, "data": data, "errors": errors}
        except Exception as e:
            return {"success": False, "data": None, "errors": [f"JSON parse error: {e}"]}

    def _extract_json(self, text: str) -> dict:
        """从LLM响应中提取JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试从代码块中提取
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找第一个 { 到最后一个 }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        raise ValueError("No valid JSON found in response")


# ============== 压缩引擎 ==============

class CompressionEngine:
    """
    压缩引擎 — 代码评分 + LLM压缩
    代码管逻辑（评分、校验），LLM管语义（压缩文本）
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        llm_call: Optional[LLMCallFunc] = None,
    ):
        self.store = store or get_memory_store()
        self.llm_call = llm_call or default_llm_call

    # ========== 反思压缩 ==========

    def compress_reflection(self, module: str) -> Dict:
        """
        压缩反思模块（反思的反思）
        当模块超过200行时触发
        """
        content = self.store.read_reflection(module)
        if not content:
            return {"success": False, "message": f"Module '{module}' is empty"}

        line_count = len(content.split("\n"))
        if line_count < 200:
            return {"success": False, "message": f"Module '{module}' only has {line_count} lines, no compression needed"}

        # LLM压缩
        prompt = REFLECTION_COMPRESS_PROMPT.format(original_content=content)
        messages = [
            {"role": "system", "content": "你是一个反思压缩助手，输出精简的SOP。"},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, "default")
        if not response:
            return {"success": False, "message": "LLM call failed"}

        # 校验压缩结果
        passed, report = self._validate_compression(content, response)
        if not passed:
            return {
                "success": False,
                "message": "Compression validation failed",
                "report": report,
            }

        # 归档原始内容
        self.store.archive_file(
            self.store.base_dir / "reflection" / f"{module}.md",
            reason=f"Compressed ({line_count} lines -> {len(response.split(chr(10)))} lines)",
        )

        # 写入压缩后的内容
        self.store.write_reflection(module, response)

        return {
            "success": True,
            "module": module,
            "before_lines": line_count,
            "after_lines": len(response.split("\n")),
            "report": report,
        }

    # ========== 旬记压缩 ==========

    def compress_period(self, year: int, month: int, period: str, scored_entries: List[Tuple[MemoryEntry, float]] = None) -> Dict:
        """
        压缩旬记
        scored_entries: [(entry, score), ...] 按分数从高到低排序
        """
        content = self.store.read_records(year, month, period)
        if not content:
            return {"success": False, "message": f"No content for {year}/{month} {period}"}

        # 构建评分信息
        score_text = ""
        if scored_entries:
            score_lines = []
            for entry, score in scored_entries[:20]:
                score_lines.append(f"- ({score:.2f}) [{entry.priority}] {entry.content[:50]}")
            score_text = "\n".join(score_lines)

        prompt = PERIOD_COMPRESS_PROMPT.format(
            period_type="旬记",
            original_content=content,
            scored_entries=score_text or "无评分信息",
        )

        messages = [
            {"role": "system", "content": "你是一个记忆压缩助手，输出精简的Markdown。"},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, "default")
        if not response:
            return {"success": False, "message": "LLM call failed"}

        # 校验
        passed, report = self._validate_compression(content, response)
        if not passed:
            return {"success": False, "message": "Validation failed", "report": report}

        # 归档原始
        original_path = self.store.get_records_path(year, month, period)
        self.store.archive_file(original_path, reason=f"Compressed {period}")

        # 写入压缩后
        self.store.write_records(year, month, period, response)

        return {
            "success": True,
            "period": f"{year}/{month} {period}",
            "report": report,
        }

    # ========== 月记压缩 ==========

    def compress_month(self, year: int, month: int) -> Dict:
        """压缩月记（合并3份旬记）"""
        periods = ["上旬", "中旬", "下旬"]
        combined = []

        for period in periods:
            content = self.store.read_records(year, month, period)
            if content:
                combined.append(f"## {period}\n\n{content}")

        if not combined:
            return {"success": False, "message": f"No content for {year}/{month}"}

        combined_content = "\n\n---\n\n".join(combined)

        prompt = COMPRESS_PROMPT.format(original_content=combined_content)
        messages = [
            {"role": "system", "content": "你是一个记忆压缩助手，输出精简的Markdown。"},
            {"role": "user", "content": prompt},
        ]

        response = self.llm_call(messages, "default")
        if not response:
            return {"success": False, "message": "LLM call failed"}

        # 写入月记
        month_path = self.store.base_dir / "records" / str(year) / f"{month:02d}" / "月记.md"
        month_path.parent.mkdir(parents=True, exist_ok=True)
        month_path.write_text(response, encoding="utf-8")

        return {"success": True, "month": f"{year}/{month}"}

    # ========== 校验 ==========

    def _validate_compression(self, original: str, compressed: str) -> Tuple[bool, Dict]:
        """
        代码层硬性校验压缩结果
        """
        janitor = get_janitor(self.store)
        return janitor.validate_compression(original, compressed)


# ============== 单例 ==============

_flush_agent: Optional[FlushAgent] = None
_compression_engine: Optional[CompressionEngine] = None

def get_flush_agent(
    store: Optional[MemoryStore] = None,
    llm_call: Optional[LLMCallFunc] = None,
) -> FlushAgent:
    global _flush_agent
    if _flush_agent is None:
        _flush_agent = FlushAgent(store, llm_call)
    return _flush_agent

def get_compression_engine(
    store: Optional[MemoryStore] = None,
    llm_call: Optional[LLMCallFunc] = None,
) -> CompressionEngine:
    global _compression_engine
    if _compression_engine is None:
        _compression_engine = CompressionEngine(store, llm_call)
    return _compression_engine
