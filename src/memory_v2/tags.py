"""
Kioxus Memory System v2 — 标签字典
标签生命周期管理、校验、alias映射、共现学习
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# ============== 配置 ==============

DEFAULT_DICT_PATH = Path(__file__).parent / "tags_dictionary.json"

# 标签生命周期状态
class TagStatus:
    ACTIVE = "active"       # 活跃，参与检索和校验
    PENDING = "pending"     # 待定，仅警告不拒绝
    DEPRECATED = "deprecated"  # 废弃，alias指向合并目标
    ARCHIVED = "archived"   # 归档，从字典移除

# ============== 数据模型 ==============

@dataclass
class TagEntry:
    """标签条目"""
    name: str
    status: str = TagStatus.ACTIVE
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    merged_to: Optional[str] = None  # 如果被合并，指向目标标签

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "merged_to": self.merged_to,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TagEntry":
        return cls(
            name=data["name"],
            status=data.get("status", TagStatus.ACTIVE),
            created_at=data.get("created_at", time.time()),
            last_used=data.get("last_used", time.time()),
            use_count=data.get("use_count", 0),
            merged_to=data.get("merged_to"),
        )


# ============== 标签字典 ==============

class TagDictionary:
    """标签字典 — 防止标签漂移，管理标签生命周期"""

    def __init__(self, dict_path: Optional[Path] = None):
        self.dict_path = dict_path or DEFAULT_DICT_PATH
        self.tags: Dict[str, TagEntry] = {}
        self.aliases: Dict[str, str] = {}  # alias -> canonical name
        self.co_occurrence: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.tag_tree: Dict[str, List[str]] = {}  # 邻域关系（从共现学习或手动定义）
        self._load()

    # ---------- 持久化 ----------

    def _load(self):
        """加载字典"""
        if not self.dict_path.exists():
            self._init_defaults()
            self._save()
            return

        try:
            with open(self.dict_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for t in data.get("tags", []):
                entry = TagEntry.from_dict(t)
                self.tags[entry.name] = entry

            self.aliases = data.get("aliases", {})
            self.co_occurrence = defaultdict(
                lambda: defaultdict(int),
                {k: defaultdict(int, v) for k, v in data.get("co_occurrence", {}).items()}
            )
            self.tag_tree = data.get("tag_tree", {})
        except Exception as e:
            print(f"[TagDict] Failed to load: {e}, initializing defaults")
            self._init_defaults()
            self._save()

    def _save(self):
        """保存字典"""
        self.dict_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "tags": [t.to_dict() for t in self.tags.values()],
            "aliases": self.aliases,
            "co_occurrence": {k: dict(v) for k, v in self.co_occurrence.items()},
            "tag_tree": self.tag_tree,
        }
        with open(self.dict_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _init_defaults(self):
        """初始化默认标签"""
        default_tags = [
            "python", "typescript", "javascript",
            "错误", "认知", "关系", "学习",
            "用户偏好", "项目配置", "代码生成",
            "决策模式", "沟通方式", "工作流",
            "记忆系统", "压缩逻辑", "代码风格",
            "语法兼容性", "技术问题", "外部事件",
        ]
        for name in default_tags:
            self.tags[name] = TagEntry(name=name)

        self.aliases = {
            "ts": "typescript",
            "js": "javascript",
            "前端": "typescript",
            "编码规范": "代码风格",
        }

    # ---------- 校验 ----------

    def validate_tags(self, tags: List[str]) -> Tuple[List[str], List[str], List[str]]:
        """
        校验标签列表
        返回: (valid_tags, unknown_tags, resolved_tags)
        """
        valid = []
        unknown = []
        resolved = []

        for tag in tags:
            tag_lower = tag.lower().strip()

            # 1. 直接匹配
            if tag_lower in self.tags:
                entry = self.tags[tag_lower]
                if entry.status in (TagStatus.ACTIVE, TagStatus.PENDING):
                    valid.append(tag_lower)
                    entry.last_used = time.time()
                    entry.use_count += 1
                elif entry.status == TagStatus.DEPRECATED and entry.merged_to:
                    resolved.append(f"{tag_lower} -> {entry.merged_to}")
                    valid.append(entry.merged_to)
                continue

            # 2. Alias 映射
            if tag_lower in self.aliases:
                canonical = self.aliases[tag_lower]
                resolved.append(f"{tag_lower} -> {canonical}")
                valid.append(canonical)
                if canonical in self.tags:
                    self.tags[canonical].last_used = time.time()
                    self.tags[canonical].use_count += 1
                continue

            # 3. 未知标签
            unknown.append(tag_lower)

        return valid, unknown, resolved

    def auto_register(self, tag: str, status: str = TagStatus.PENDING) -> TagEntry:
        """自动注册新标签（待定状态）"""
        entry = TagEntry(name=tag, status=status)
        self.tags[tag] = entry
        self._save()
        return entry

    def merge_tags(self, source: str, target: str):
        """合并标签：source -> target"""
        source = source.lower().strip()
        target = target.lower().strip()

        # 确保目标存在
        if target not in self.tags:
            self.tags[target] = TagEntry(name=target)

        # 标记源为废弃
        if source in self.tags:
            self.tags[source].status = TagStatus.DEPRECATED
            self.tags[source].merged_to = target

        # 添加alias
        self.aliases[source] = target
        self._save()

    # ---------- 共现学习 ----------

    def record_co_occurrence(self, tags: List[str]):
        """记录标签共现"""
        for i, t1 in enumerate(tags):
            for t2 in tags[i + 1:]:
                self.co_occurrence[t1][t2] += 1
                self.co_occurrence[t2][t1] += 1

        # 检查是否有新的邻域关系需要固化
        self._maybe_build_tag_tree(tags)
        self._save()

    def _maybe_build_tag_tree(self, tags: List[str]):
        """当共现次数超过阈值时，固化为tag_tree邻域关系"""
        THRESHOLD = 5
        for t1 in tags:
            for t2, count in self.co_occurrence.get(t1, {}).items():
                if count >= THRESHOLD:
                    if t1 not in self.tag_tree:
                        self.tag_tree[t1] = []
                    if t2 not in self.tag_tree[t1]:
                        self.tag_tree[t1].append(t2)

                    # 双向
                    if t2 not in self.tag_tree:
                        self.tag_tree[t2] = []
                    if t1 not in self.tag_tree[t2]:
                        self.tag_tree[t2].append(t1)

    def get_adjacent_tags(self, tag: str) -> List[str]:
        """获取标签的邻域标签"""
        return self.tag_tree.get(tag, [])

    # ---------- 维护 ----------

    def get_bloat_report(self) -> Dict:
        """生成标签膨胀报告"""
        now = time.time()
        growing = []   # 增长最快
        unused = []    # 从未使用
        candidates = []  # 近义词候选

        for name, entry in self.tags.items():
            if entry.use_count == 0 and entry.status == TagStatus.ACTIVE:
                unused.append(name)
            if entry.use_count > 5:
                growing.append((name, entry.use_count))

        growing.sort(key=lambda x: x[1], reverse=True)

        # 检查近义词（简单：看alias中是否有指向同一目标的多个源）
        target_sources = defaultdict(list)
        for alias, target in self.aliases.items():
            target_sources[target].append(alias)
        for target, sources in target_sources.items():
            if len(sources) > 1:
                candidates.append({"target": target, "sources": sources})

        return {
            "total_tags": len(self.tags),
            "active": sum(1 for t in self.tags.values() if t.status == TagStatus.ACTIVE),
            "growing_fastest": growing[:10],
            "never_used": unused,
            "merge_candidates": candidates,
        }

    def cleanup(self):
        """清理归档标签"""
        to_remove = [
            name for name, entry in self.tags.items()
            if entry.status == TagStatus.ARCHIVED
        ]
        for name in to_remove:
            del self.tags[name]
        self._save()
        return len(to_remove)

    # ---------- 查询 ----------

    def get_active_tags(self) -> List[str]:
        """获取所有活跃标签"""
        return [name for name, entry in self.tags.items() if entry.status == TagStatus.ACTIVE]

    def search_tags(self, query: str) -> List[str]:
        """搜索标签（模糊匹配）"""
        query = query.lower()
        results = []
        for name in self.tags:
            if query in name:
                results.append(name)
        # 也搜索alias
        for alias in self.aliases:
            if query in alias:
                results.append(f"{alias} -> {self.aliases[alias]}")
        return results


# ============== 单例 ==============

_instance: Optional[TagDictionary] = None

def get_tag_dictionary(dict_path: Optional[Path] = None) -> TagDictionary:
    global _instance
    if _instance is None:
        _instance = TagDictionary(dict_path)
    return _instance
