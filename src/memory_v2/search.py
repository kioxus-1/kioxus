"""
Kioxus Memory System v2 — 检索系统（精简版）
BM25检索 + 关键词提取

精简原则：
  - 只保留BM25核心
  - 去掉时序衰减、RRF融合等花哨功能
  - 先保证"能找到"，再考虑高级功能
"""

import re
import math
import time
from typing import List, Dict, Optional
from dataclasses import dataclass


# ============== BM25 实现 ==============

class SimpleBM25:
    """轻量BM25，无外部依赖"""

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Dict] = []
        self.avgdl = 0
        self.doc_lengths: List[int] = []
        self.doc_freqs: Dict[str, int] = {}
        self.num_docs = 0

    def add_doc(self, doc_id: str, text: str, metadata: dict = None):
        tokens = self._tokenize(text)
        self.documents.append({
            "id": doc_id,
            "text": text,
            "tokens": tokens,
            "length": len(tokens),
            "metadata": metadata or {},
        })
        self.doc_lengths.append(len(tokens))
        for token in set(tokens):
            self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
        self.num_docs += 1
        self.avgdl = sum(self.doc_lengths) / self.num_docs if self.num_docs > 0 else 0

    def _tokenize(self, text: str) -> List[str]:
        """简单分词：提取中英文词和数字"""
        text = text.lower()
        tokens = []
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                tokens.append(char)
        tokens.extend(re.findall(r'[a-z0-9_]+', text))
        return tokens

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.documents:
            return []
        query_tokens = self._tokenize(query)
        scores = []
        for doc in self.documents:
            score = self._calc_bm25(doc, query_tokens)
            if score > 0:
                scores.append({
                    "doc_id": doc["id"],
                    "score": score,
                    "text": doc["text"][:300],
                    "metadata": doc["metadata"],
                })
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    def _calc_bm25(self, doc: dict, query_tokens: List[str]) -> float:
        doc_tokens = doc["tokens"]
        doc_len = doc["length"]
        score = 0.0
        for q_token in query_tokens:
            if q_token not in doc_tokens:
                continue
            tf = doc_tokens.count(q_token)
            df = self.doc_freqs.get(q_token, 1)
            idf = math.log((self.num_docs - df + 0.5) / (df + 0.5) + 1)
            tf_component = (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            )
            score += idf * tf_component
        return score

    def clear(self):
        self.documents.clear()
        self.doc_lengths.clear()
        self.doc_freqs.clear()
        self.num_docs = 0
        self.avgdl = 0


# ============== 关键词提取 ==============

STOPWORDS = set(
    "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 "
    "自己 这 他 她 它 们 那 里 为 什么 吗 吧 呢 啊 呀 哦 嗯 把 被 让 给 对 从 跟 向 "
    "但 而 如果 因为 所以 虽然 可以 已经 还 又 再 才 就是 只是 还是 或者 这个 那个".split()
)


def extract_keywords_simple(text: str) -> List[str]:
    """简易关键词提取（不依赖外部库）"""
    keywords = []

    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
    for phrase in chinese_chars:
        if len(phrase) >= 2 and phrase not in STOPWORDS:
            keywords.append(phrase)
        for i in range(len(phrase) - 1):
            sub2 = phrase[i:i+2]
            if sub2 not in STOPWORDS:
                keywords.append(sub2)

    english_words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text)
    keywords.extend(w.lower() for w in english_words if len(w) > 1)

    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)

    return result


# ============== 检索引擎 ==============

class MemorySearch:
    """记忆检索引擎"""

    def __init__(self):
        self.index = SimpleBM25()

    def index_file(self, doc_id: str, content: str, metadata: dict = None):
        """索引单个文件"""
        self.index.add_doc(doc_id, content, metadata)

    def index_memory_store(self, store) -> int:
        """从 MemoryStore 重建索引"""
        self.index.clear()
        count = 0

        # 索引反思层
        for module in store.list_reflection_modules():
            content = store.read_reflection(module)
            if content:
                self.index.add_doc(
                    f"reflection/{module}",
                    content,
                    {"layer": "reflection", "module": module},
                )
                count += 1

        # 索引记录层
        records_dir = store.base_dir / "records"
        if records_dir.exists():
            for md_file in records_dir.rglob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                rel_path = str(md_file.relative_to(store.base_dir))
                self.index.add_doc(
                    rel_path,
                    content,
                    {"layer": "records", "path": rel_path},
                )
                count += 1

        # 索引每日日志
        daily_dir = store.base_dir / "daily"
        if daily_dir.exists():
            for md_file in daily_dir.glob("*.md"):
                content = md_file.read_text(encoding="utf-8")
                rel_path = str(md_file.relative_to(store.base_dir))
                self.index.add_doc(
                    rel_path,
                    content,
                    {"layer": "daily", "path": rel_path},
                )
                count += 1

        return count

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """检索"""
        return self.index.search(query, top_k)

    def search_with_extraction(self, query: str, top_k: int = 5) -> List[Dict]:
        """提取关键词 + 搜索"""
        keywords = extract_keywords_simple(query)
        if not keywords:
            return self.search(query, top_k)

        # 合并关键词搜索结果
        all_results = {}
        for kw in keywords[:5]:  # 最多5个关键词
            results = self.index.search(kw, top_k)
            for r in results:
                doc_id = r["doc_id"]
                if doc_id in all_results:
                    all_results[doc_id]["score"] += r["score"]
                else:
                    all_results[doc_id] = r.copy()

        merged = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)
        return merged[:top_k]

    def get_stats(self) -> Dict:
        return {
            "indexed_docs": len(self.index.documents),
            "vocab_size": len(self.index.doc_freqs),
        }


# ============== 单例 ==============

_instance: Optional[MemorySearch] = None


def get_search() -> MemorySearch:
    global _instance
    if _instance is None:
        _instance = MemorySearch()
    return _instance
