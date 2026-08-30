"""
Kioxus Memory v2 — 核心模块测试
测试 memory.py, search.py, tags.py, router.py
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.tags import TagDictionary, TagEntry, TagStatus
from memory.memory import MemoryStore, MemoryEntry, parse_frontmatter, build_frontmatter
from memory.search import SimpleBM25, MemorySearch, extract_keywords_simple
from memory.router import MemoryRouter, estimate_tokens


# ============== 临时目录 fixture ==============

class TempDir:
    def __init__(self):
        self.path = Path(tempfile.mkdtemp(prefix="kioxus_test_"))
    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)


# ============== TagDictionary 测试 ==============

def test_tag_dictionary():
    """测试标签字典"""
    tmp = TempDir()
    try:
        dict_path = tmp.path / "tags.json"
        td = TagDictionary(dict_path)

        # 应有预设标签
        active = td.get_active_tags()
        assert len(active) > 0, "应有预设标签"

        # auto_register新标签
        entry = td.auto_register("test_tag", status="active")
        assert entry is not None
        assert entry.name == "test_tag"

        # validate_tags
        valid, invalid, suggestions = td.validate_tags(["python", "nonexistent_tag"])
        assert "python" in valid
        assert "nonexistent_tag" in invalid

        # search_tags
        results = td.search_tags("python")
        assert len(results) > 0

        print("PASS test_tag_dictionary")
    finally:
        tmp.cleanup()


# ============== MemoryStore 测试 ==============

def test_memory_store():
    """测试记忆存储"""
    tmp = TempDir()
    try:
        store = MemoryStore(tmp.path)

        # 写入today.md
        store.append_to_today("[记录] 测试内容")
        content = store.read_today()
        assert "测试内容" in content

        # 写入core.md（需要MemoryEntry对象）
        entry = MemoryEntry(layer="core", content="[事实] 用户叫测试", tags=["用户"], priority="P0")
        store.append_to_core(entry)
        content = store.read_core()
        assert "测试" in content

        # 写入reflection
        store.write_reflection("测试模块", "# 测试反思\n\n这是测试内容")
        content = store.read_reflection("测试模块")
        assert "测试反思" in content

        # 列出反思模块
        modules = store.list_reflection_modules()
        assert "测试模块" in modules

        # clear_today
        store.clear_today()
        content = store.read_today()
        assert content == "" or "测试内容" not in content

        print("PASS test_memory_store")
    finally:
        tmp.cleanup()


def test_frontmatter():
    """测试Frontmatter解析"""
    content = """---
tags: [python, test]
priority: P0
---
# 标题

内容"""

    frontmatter, body = parse_frontmatter(content)
    assert frontmatter["tags"] == ["python", "test"]
    assert frontmatter["priority"] == "P0"
    assert "标题" in body
    assert "内容" in body

    # 重建
    rebuilt = build_frontmatter(frontmatter)
    assert "python" in rebuilt

    print("PASS test_frontmatter")


# ============== SimpleBM25 测试 ==============

def test_bm25():
    """测试BM25检索"""
    bm25 = SimpleBM25()

    # 添加文档
    bm25.add_doc("doc1", "Python一种编程语言", {"tags": ["python"]})
    bm25.add_doc("doc2", "JavaScript用于前端开发", {"tags": ["javascript"]})
    bm25.add_doc("doc3", "Python和JavaScript都很流行", {"tags": ["python", "javascript"]})

    # 搜索
    results = bm25.search("Python", top_k=3)
    assert len(results) > 0
    assert results[0]["doc_id"] in ("doc1", "doc3")

    # 中文搜索
    results = bm25.search("编程", top_k=3)
    assert len(results) > 0

    # 空查询
    results = bm25.search("", top_k=3)
    assert len(results) == 0

    # clear
    bm25.clear()
    assert bm25.num_docs == 0

    print("PASS test_bm25")


def test_bm25_tokenizer():
    """测试BM25分词器"""
    bm25 = SimpleBM25()

    # 中文分词（逐字）
    tokens = bm25._tokenize("你好世界")
    assert len(tokens) == 4

    # 英文分词
    tokens = bm25._tokenize("hello world")
    assert "hello" in tokens
    assert "world" in tokens

    # 大小写归一化
    tokens = bm25._tokenize("Python PYTHON python")
    assert all(t == "python" for t in tokens if t.isalpha())

    print("PASS test_bm25_tokenizer")


# ============== 关键词提取测试 ==============

def test_keyword_extraction():
    """测试关键词提取"""
    # 中文
    keywords = extract_keywords_simple("Python一种编程语言")
    assert any("python" in k.lower() for k in keywords)
    assert len(keywords) > 0

    # 英文
    keywords = extract_keywords_simple("hello world test")
    assert "hello" in keywords
    assert "world" in keywords

    # 去重
    keywords = extract_keywords_simple("Python Python Python")
    python_count = sum(1 for k in keywords if k.lower() == "python")
    assert python_count == 1

    print("PASS test_keyword_extraction")


# ============== MemorySearch 测试 ==============

def test_memory_search():
    """测试记忆检索"""
    search = MemorySearch()

    # 索引文件
    search.index_file("doc1", "Python编程语言", {"layer": "core"})
    search.index_file("doc2", "JavaScript前端开发", {"layer": "reflection"})

    # 搜索
    results = search.search("Python", top_k=5)
    assert len(results) > 0
    assert results[0]["doc_id"] == "doc1"

    # 关键词搜索
    results = search.search_with_extraction("编程语言", top_k=5)
    assert len(results) > 0

    # 统计
    stats = search.get_stats()
    assert stats["indexed_docs"] == 2

    print("PASS test_memory_search")


# ============== estimate_tokens 测试 ==============

def test_estimate_tokens():
    """测试Token估算"""
    assert estimate_tokens("") == 0
    assert 0 < estimate_tokens("你好世界") < 10
    assert 0 < estimate_tokens("hello world") < 10
    assert estimate_tokens("你好world") > 0

    print("PASS test_estimate_tokens")


# ============== MemoryRouter 测试 ==============

def test_memory_router():
    """测试记忆路由器"""
    tmp = TempDir()
    try:
        store = MemoryStore(tmp.path)
        # 写入core.md（需要MemoryEntry对象）
        entry = MemoryEntry(layer="core", content="[事实] 用户叫测试", tags=["用户"], priority="P0")
        store.append_to_core(entry)
        store.append_to_today("[记录] 今天聊了Python")

        search = MemorySearch()
        tags = TagDictionary(tmp.path / "tags.json")
        router = MemoryRouter(store, search, tags)

        # 构建上下文
        ctx = router.build_context("你好")
        assert "context" in ctx
        assert "tokens" in ctx
        assert "breakdown" in ctx

        # 扩展模式
        ctx_ext = router.build_context("帮我写Python代码", extended=True)
        assert ctx_ext["tokens"] > 0

        print("PASS test_memory_router")
    finally:
        tmp.cleanup()


if __name__ == "__main__":
    print("=" * 50)
    print("  Memory v2 测试")
    print("=" * 50)

    tests = [
        test_tag_dictionary,
        test_memory_store,
        test_frontmatter,
        test_bm25,
        test_bm25_tokenizer,
        test_keyword_extraction,
        test_memory_search,
        test_estimate_tokens,
        test_memory_router,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 50)
    print(f"Result: {passed} passed, {failed} failed")
    print("=" * 50)
    sys.exit(1 if failed else 0)
