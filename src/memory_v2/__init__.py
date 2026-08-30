"""
Kioxus Memory System v2（精简版）
四层记忆架构 + 代码/LLM职责分离

架构：
  核心层 (core.md)        — 每次对话强制注入，稳定不轻易变
  反思层 (reflection/)    — 认知迭代，权重高于记录，模块动态增加
  记录层 (records/)       — 日志→旬记→月记→年记，分层压缩
  短期层 (today.md)       — 今日内容，每天清空

核心组件：
  TagDictionary   — 标签字典，防漂移，生命周期管理
  MemoryStore     — 四层文件存储
  MemorySearch    — BM25检索
  MemoryRouter    — 上下文组装，分层Token预算
  MemoryJanitor   — Flush/结算/压缩/归档/遗忘

设计原则：
  代码管逻辑，LLM管语义
  压缩不遗忘
  只记改变未来行为的东西
"""

from .tags import (
    TagDictionary, TagEntry, TagStatus,
    get_tag_dictionary,
)

from .memory import (
    MemoryStore, MemoryEntry,
    parse_frontmatter, build_frontmatter,
    get_memory_store,
)

from .search import (
    MemorySearch, SimpleBM25,
    extract_keywords_simple,
    get_search,
)

from .router import (
    MemoryRouter,
    estimate_tokens, truncate_to_budget,
    get_router,
)

from .janitor import (
    MemoryJanitor, FileLock,
    validate_flush_output,
    get_janitor,
)

from .compressor import (
    FlushAgent, CompressionEngine,
    get_flush_agent, get_compression_engine,
    LLMCallFunc,
)

__version__ = "2.1.0"

__all__ = [
    # 标签
    "TagDictionary", "TagEntry", "TagStatus", "get_tag_dictionary",
    # 存储
    "MemoryStore", "MemoryEntry", "parse_frontmatter", "build_frontmatter", "get_memory_store",
    # 检索
    "MemorySearch", "SimpleBM25", "extract_keywords_simple", "get_search",
    # 路由
    "MemoryRouter", "estimate_tokens", "truncate_to_budget", "get_router",
    # 维护
    "MemoryJanitor", "FileLock", "validate_flush_output", "get_janitor",
    # LLM压缩
    "FlushAgent", "CompressionEngine", "get_flush_agent", "get_compression_engine", "LLMCallFunc",
    # 统一接口
    "get_memory_system", "save_memory",
]


def get_memory_system(base_dir=None) -> dict:
    """
    获取完整的记忆系统
    返回所有组件的实例
    """
    from pathlib import Path

    store = get_memory_store(Path(base_dir) if base_dir else None)
    tags = get_tag_dictionary()
    search = get_search()
    router = get_router(store, search, tags)
    janitor = get_janitor(store, tags)

    return {
        "store": store,
        "tags": tags,
        "search": search,
        "router": router,
        "janitor": janitor,
    }


def save_memory(layer: str, content: str, tags: list = None,
                priority: str = "P2", module: str = None,
                source_type: str = "agent") -> dict:
    """
    统一的记忆写入接口

    参数:
        layer: 写入层级 (core/reflection/records/short-term)
        content: 记忆内容
        tags: 标签列表
        priority: 优先级 (P0-P3)
        module: 反思模块名（仅reflection层）
        source_type: 来源类型
    """
    from pathlib import Path
    from datetime import datetime

    try:
        store = get_memory_store()
        tags_dict = get_tag_dictionary()

        # 构建条目
        entry = MemoryEntry(
            content=content,
            tags=tags or [],
            priority=priority,
            source_type=source_type,
            created_at=datetime.now().isoformat(),
        )

        # 根据层级写入
        if layer == "core":
            store.append_core(content, tags=tags or [], priority=priority)
        elif layer == "reflection":
            module_name = module or "general"
            store.write_reflection(module_name, content)
        elif layer == "records":
            today = datetime.now().strftime("%Y-%m-%d")
            store.write_daily(today, content)
        elif layer == "short-term":
            store.append_today(content)
        else:
            return {"success": False, "errors": [f"未知层级: {layer}"]}

        # 更新标签
        for tag in (tags or []):
            tags_dict.touch(tag, increment=1)

        return {"success": True, "layer": layer}

    except Exception as e:
        return {"success": False, "errors": [str(e)]}
