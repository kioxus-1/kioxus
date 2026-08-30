"""
Kioxus Memory System v2 — Memory Router
上下文组装、分层Token预算、主动注入
"""

import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .memory import MemoryStore, get_memory_store
from .search import MemorySearch, get_search, extract_keywords_simple
from .tags import TagDictionary, get_tag_dictionary

# ============== Token 估算 ==============

def estimate_tokens(text: str) -> int:
    """估算token数（中文~2字符/token，英文~4字符/token）"""
    if not text:
        return 0
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other = len(text) - chinese
    return max(1, chinese // 2 + other // 4)


def truncate_to_budget(text: str, max_tokens: int) -> str:
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


# ============== Memory Router ==============

class MemoryRouter:
    """
    记忆路由器 — 代码层负责检索、组装、截断
    不让LLM自己决定"要不要检索"
    """

    # 分层Token预算（占总上下文的比例）
    LAYER_BUDGETS = {
        "core": 0.05,        # 5%
        "today": 0.05,       # 5%
        "overview": 0.01,    # 1%
        "reflection": 0.10,  # 10%
        "records": 0.10,     # 10%
    }
    # 总预算
    TOTAL_BUDGET_RATIO = 0.30  # 30%
    EXTENDED_BUDGET_RATIO = 0.40  # 40%（复杂任务）

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        search: Optional[MemorySearch] = None,
        tags: Optional[TagDictionary] = None,
        max_context_tokens: int = 8000,
    ):
        self.store = store or get_memory_store()
        self.search = search or get_search()
        self.tags = tags or get_tag_dictionary()
        self.max_context_tokens = max_context_tokens

    @property
    def total_budget(self) -> int:
        return int(self.max_context_tokens * self.TOTAL_BUDGET_RATIO)

    @property
    def extended_budget(self) -> int:
        return int(self.max_context_tokens * self.EXTENDED_BUDGET_RATIO)

    def layer_budget(self, layer: str) -> int:
        return int(self.max_context_tokens * self.LAYER_BUDGETS.get(layer, 0))

    # ========== 核心注入 ==========

    def build_context(
        self,
        user_message: str = "",
        extended: bool = False,
    ) -> Dict:
        """
        构建完整记忆上下文
        返回: {"context": str, "tokens": int, "breakdown": dict, "search_results": list}
        """
        budget = self.extended_budget if extended else self.total_budget
        breakdown = {}
        parts = []
        used_tokens = 0

        # 1. core.md（始终注入）
        core_content = self.store.read_core()
        if core_content:
            core_budget = self.layer_budget("core")
            core_truncated = truncate_to_budget(core_content, core_budget)
            parts.append(f"[核心记忆]\n{core_truncated}")
            core_tokens = estimate_tokens(core_truncated)
            used_tokens += core_tokens
            breakdown["core"] = {"tokens": core_tokens, "truncated": len(core_truncated) < len(core_content)}

        # 2. today.md（始终注入）
        today_content = self.store.read_today()
        if today_content:
            today_budget = self.layer_budget("today")
            today_truncated = truncate_to_budget(today_content, today_budget)
            parts.append(f"[今日记忆]\n{today_truncated}")
            today_tokens = estimate_tokens(today_truncated)
            used_tokens += today_tokens
            breakdown["today"] = {"tokens": today_tokens}

        # 3. overview.md（始终注入）
        overview_content = self.store.read_overview()
        if overview_content:
            overview_budget = self.layer_budget("overview")
            overview_truncated = truncate_to_budget(overview_content, overview_budget)
            parts.append(f"[记忆概览]\n{overview_truncated}")
            overview_tokens = estimate_tokens(overview_truncated)
            used_tokens += overview_tokens
            breakdown["overview"] = {"tokens": overview_tokens}

        # 4. 检索反思层和记录层（按需）
        search_results = []
        remaining_budget = budget - used_tokens

        if user_message and remaining_budget > 0:
            # 提取关键词
            keywords = extract_keywords_simple(user_message)

            # 检索
            results = self.search.search_with_extraction(user_message, top_k=5)
            search_results = results

            if results:
                # 按层分组
                reflection_results = [r for r in results if r.get("metadata", {}).get("layer") == "reflection"]
                records_results = [r for r in results if r.get("metadata", {}).get("layer") in ("records", "daily")]

                # 注入反思层结果
                if reflection_results:
                    ref_budget = min(self.layer_budget("reflection"), remaining_budget // 2)
                    ref_text = self._format_search_results(reflection_results, "反思记忆", ref_budget)
                    if ref_text:
                        parts.append(ref_text)
                        ref_tokens = estimate_tokens(ref_text)
                        used_tokens += ref_tokens
                        remaining_budget -= ref_tokens
                        breakdown["reflection"] = {"tokens": ref_tokens, "hits": len(reflection_results)}

                # 注入记录层结果
                if records_results and remaining_budget > 0:
                    rec_budget = min(self.layer_budget("records"), remaining_budget)
                    rec_text = self._format_search_results(records_results, "记录记忆", rec_budget)
                    if rec_text:
                        parts.append(rec_text)
                        rec_tokens = estimate_tokens(rec_text)
                        used_tokens += rec_tokens
                        breakdown["records"] = {"tokens": rec_tokens, "hits": len(records_results)}

        context = "\n\n".join(parts)

        return {
            "context": context,
            "tokens": used_tokens,
            "budget": budget,
            "utilization": round(used_tokens / max(budget, 1), 2),
            "breakdown": breakdown,
            "search_results": search_results,
        }

    def build_messages(
        self,
        messages: List[dict],
        user_message: str = "",
        extended: bool = False,
    ) -> List[dict]:
        """将记忆注入到消息列表（用于API调用）"""
        result = self.build_context(user_message, extended)
        context = result["context"]

        if not context:
            return messages

        injected = []
        memory_inserted = False

        for msg in messages:
            if msg.get("role") == "system" and not memory_inserted:
                injected.append(msg)
                injected.append({
                    "role": "system",
                    "content": f"[记忆上下文]\n{context}\n[/记忆上下文]",
                })
                memory_inserted = True
            else:
                injected.append(msg)

        if not memory_inserted:
            injected.insert(0, {
                "role": "system",
                "content": f"[记忆上下文]\n{context}\n[/记忆上下文]",
            })

        return injected

    # ========== 辅助 ==========

    def _format_search_results(self, results: List[Dict], label: str, budget: int) -> str:
        """格式化检索结果"""
        if not results:
            return ""

        lines = [f"[{label}]"]
        current_tokens = 0

        for r in results:
            text = r.get("text", "")[:200]
            score = r.get("score", 0)
            line = f"- ({score:.2f}) {text}"
            line_tokens = estimate_tokens(line)
            if current_tokens + line_tokens > budget:
                break
            lines.append(line)
            current_tokens += line_tokens

        return "\n".join(lines) if len(lines) > 1 else ""

    def refresh_index(self) -> int:
        """刷新检索索引"""
        return self.search.index_memory_store(self.store)


# ============== 单例 ==============

_instance: Optional[MemoryRouter] = None

def get_router(
    store: Optional[MemoryStore] = None,
    search: Optional[MemorySearch] = None,
    tags: Optional[TagDictionary] = None,
) -> MemoryRouter:
    global _instance
    if _instance is None:
        _instance = MemoryRouter(store, search, tags)
    return _instance
