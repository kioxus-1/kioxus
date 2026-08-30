"""
Kioxus Memory System v2 — 四层记忆存储
core.md / reflection/ / records/ / today.md
基于Markdown文件 + YAML Frontmatter
"""

import json
import re
import time
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# ============== 配置 ==============

DEFAULT_MEMORY_DIR = Path(__file__).parent / "data"

CORE_FILE = "core.md"
OVERVIEW_FILE = "overview.md"
REFLECTION_DIR = "reflection"
RECORDS_DIR = "records"
SHORT_TERM_DIR = "short-term"
TODAY_FILE = "today.md"
DAILY_DIR = "daily"
ARCHIVE_DIR = "archive"

# Frontmatter 解析
FRONTMATTER_PATTERN = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$",
    re.DOTALL
)

# ============== Frontmatter 解析 ==============

def parse_frontmatter(content: str) -> tuple:
    """解析 YAML Frontmatter，返回 (metadata_dict, body)"""
    match = FRONTMATTER_PATTERN.match(content.strip())
    if not match:
        return {}, content

    raw_yaml = match.group(1)
    body = match.group(2)

    # 简易YAML解析（不依赖外部库）
    metadata = {}
    for line in raw_yaml.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            # 解析列表 [a, b, c]
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                metadata[key] = items
            # 解析数字
            elif value.isdigit():
                metadata[key] = int(value)
            # 解析null
            elif value.lower() == "null":
                metadata[key] = None
            # 解析布尔
            elif value.lower() in ("true", "false"):
                metadata[key] = value.lower() == "true"
            else:
                metadata[key] = value.strip("'\"")

    return metadata, body


def build_frontmatter(metadata: dict) -> str:
    """构建 YAML Frontmatter 字符串"""
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


# ============== 记忆条目 ==============

@dataclass
class MemoryEntry:
    """记忆条目"""
    layer: str              # core / reflection / records / short-term
    content: str            # 正文内容
    tags: List[str] = field(default_factory=list)
    priority: str = "P2"    # P0/P1/P2/P3
    source: Optional[str] = None       # 来源对话ID
    source_type: str = "agent"         # user / agent / external
    created_at: float = field(default_factory=time.time)
    recall_count: int = 0
    last_recalled: Optional[float] = None
    # 反思层专用
    module: Optional[str] = None
    # 记录层专用
    period: Optional[str] = None
    date_range: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "layer": self.layer,
            "content": self.content,
            "tags": self.tags,
            "priority": self.priority,
            "source": self.source,
            "source_type": self.source_type,
            "created_at": self.created_at,
            "recall_count": self.recall_count,
            "last_recalled": self.last_recalled,
        }
        if self.module:
            d["module"] = self.module
        if self.period:
            d["period"] = self.period
        if self.date_range:
            d["date_range"] = self.date_range
        return d


# ============== 四层存储 ==============

class MemoryStore:
    """四层记忆文件存储"""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or DEFAULT_MEMORY_DIR
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录结构存在"""
        for subdir in [
            REFLECTION_DIR,
            f"{RECORDS_DIR}/2026/07",
            SHORT_TERM_DIR,
            DAILY_DIR,
            ARCHIVE_DIR,
        ]:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)

    # ========== 核心层 ==========

    def read_core(self) -> str:
        """读取 core.md"""
        path = self.base_dir / CORE_FILE
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_core(self, content: str):
        """写入 core.md"""
        path = self.base_dir / CORE_FILE
        path.write_text(content, encoding="utf-8")

    def append_to_core(self, entry: MemoryEntry):
        """追加到 core.md"""
        current = self.read_core()
        entry_text = self._format_entry(entry)
        if current:
            current += "\n\n" + entry_text
        else:
            current = f"# 核心记忆\n\n{entry_text}"
        self.write_core(current)

    # ========== 反思层 ==========

    def read_reflection(self, module: str) -> str:
        """读取反思模块文件"""
        path = self.base_dir / REFLECTION_DIR / f"{module}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_reflection(self, module: str, content: str):
        """写入反思模块文件"""
        path = self.base_dir / REFLECTION_DIR / f"{module}.md"
        path.write_text(content, encoding="utf-8")

    def append_to_reflection(self, entry: MemoryEntry):
        """追加到反思模块"""
        module = entry.module or "通用"
        current = self.read_reflection(module)

        # 检查行数阈值
        if current:
            line_count = len(current.split("\n"))
            if line_count >= 200:
                # 触发膨胀控制：需要"反思的反思"
                return {"action": "compress_needed", "module": module, "lines": line_count}

        entry_text = self._format_entry(entry)
        if current:
            current += "\n\n" + entry_text
        else:
            frontmatter = build_frontmatter({
                "module": module,
                "tags": entry.tags,
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
            })
            current = f"{frontmatter}\n\n# {module}\n\n{entry_text}"
        self.write_reflection(module, current)
        return {"action": "written", "module": module}

    def list_reflection_modules(self) -> List[str]:
        """列出所有反思模块"""
        ref_dir = self.base_dir / REFLECTION_DIR
        return [f.stem for f in ref_dir.glob("*.md") if f.name != "index.md"]

    # ========== 记录层 ==========

    def get_records_path(self, year: int, month: int, period: str) -> Path:
        """获取旬记文件路径"""
        return self.base_dir / RECORDS_DIR / str(year) / f"{month:02d}" / f"{period}.md"

    def read_records(self, year: int, month: int, period: str) -> str:
        """读取旬记"""
        path = self.get_records_path(year, month, period)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_records(self, year: int, month: int, period: str, content: str):
        """写入旬记"""
        path = self.get_records_path(year, month, period)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def get_period_for_date(dt: datetime) -> str:
        """获取日期对应的旬"""
        day = dt.day
        if day <= 10:
            return "上旬"
        elif day <= 20:
            return "中旬"
        else:
            return "下旬"

    # ========== 短期层 ==========

    def read_today(self) -> str:
        """读取 today.md"""
        path = self.base_dir / SHORT_TERM_DIR / TODAY_FILE
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_today(self, content: str):
        """写入 today.md"""
        path = self.base_dir / SHORT_TERM_DIR / TODAY_FILE
        path.write_text(content, encoding="utf-8")

    def append_to_today(self, text: str):
        """追加到 today.md"""
        current = self.read_today()
        timestamp = datetime.now().strftime("%H:%M")
        entry = f"[{timestamp}] {text}"
        if current:
            current += "\n" + entry
        else:
            current = f"# 今日记忆\n\n{entry}"
        self.write_today(current)

    def clear_today(self):
        """清空 today.md"""
        self.write_today("")

    # ========== 每日日志 ==========

    def read_daily(self, date_str: str) -> str:
        """读取 daily/YYYY-MM-DD.md"""
        path = self.base_dir / DAILY_DIR / f"{date_str}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_daily(self, date_str: str, content: str):
        """写入 daily/YYYY-MM-DD.md"""
        path = self.base_dir / DAILY_DIR / f"{date_str}.md"
        path.write_text(content, encoding="utf-8")

    # ========== overview.md ==========

    def read_overview(self) -> str:
        """读取 overview.md"""
        path = self.base_dir / OVERVIEW_FILE
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_overview(self, content: str):
        """写入 overview.md"""
        path = self.base_dir / OVERVIEW_FILE
        path.write_text(content, encoding="utf-8")

    # ========== 归档 ==========

    def archive_file(self, source_path: Path, reason: str = ""):
        """将文件移入归档区"""
        if not source_path.exists():
            return
        archive_path = self.base_dir / ARCHIVE_DIR / source_path.name
        # 避免重名
        if archive_path.exists():
            stem = source_path.stem
            suffix = source_path.suffix
            archive_path = self.base_dir / ARCHIVE_DIR / f"{stem}_{int(time.time())}{suffix}"
        shutil.move(str(source_path), str(archive_path))

        # 写入归档元数据
        meta_path = archive_path.with_suffix(".meta.json")
        meta = {
            "original_path": str(source_path),
            "archived_at": time.time(),
            "reason": reason,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def archive_memory_entry(self, entry: MemoryEntry, source_file: Path, reason: str = ""):
        """从源文件中移除一条记忆并归档"""
        # 读取源文件
        content = source_file.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(content)

        # 找到并移除匹配的内容段
        entry_text = self._format_entry(entry)
        if entry_text in body:
            body = body.replace(entry_text, "").strip()
            # 清理多余空行
            body = re.sub(r"\n{3,}", "\n\n", body)
            # 写回源文件
            if metadata:
                new_content = build_frontmatter(metadata) + "\n\n" + body
            else:
                new_content = body
            source_file.write_text(new_content, encoding="utf-8")

        # 写入归档
        archive_dir = self.base_dir / ARCHIVE_DIR
        archive_file = archive_dir / f"entry_{int(time.time())}.md"
        archive_content = f"<!-- archived: {reason} -->\n\n{build_frontmatter(entry.to_dict())}\n\n{entry.content}"
        archive_file.write_text(archive_content, encoding="utf-8")

    # ========== 工具方法 ==========

    def _format_entry(self, entry: MemoryEntry) -> str:
        """格式化记忆条目为Markdown"""
        lines = []
        # 事实和行动
        lines.append(entry.content)
        # 标签
        if entry.tags:
            tags_str = " ".join(f"#{t}" for t in entry.tags)
            lines.append(f"\ntags: {tags_str}")
        # 元信息
        date_str = datetime.fromtimestamp(entry.created_at).strftime("%Y-%m-%d %H:%M")
        lines.append(f"created: {date_str}")
        if entry.source:
            lines.append(f"source: {entry.source}")
        lines.append(f"priority: {entry.priority}")
        lines.append("---")
        return "\n".join(lines)

    def count_lines(self, layer: str, module: str = None) -> int:
        """统计文件行数"""
        if layer == "core":
            content = self.read_core()
        elif layer == "reflection" and module:
            content = self.read_reflection(module)
        elif layer == "today":
            content = self.read_today()
        else:
            return 0
        return len(content.split("\n")) if content else 0

    def get_memory_stats(self) -> Dict:
        """获取记忆统计"""
        stats = {
            "core_lines": self.count_lines("core"),
            "today_lines": self.count_lines("today"),
            "reflection_modules": {},
            "daily_files": 0,
            "archive_files": 0,
        }

        # 反思层统计
        for module in self.list_reflection_modules():
            stats["reflection_modules"][module] = self.count_lines("reflection", module)

        # 每日日志统计
        daily_dir = self.base_dir / DAILY_DIR
        stats["daily_files"] = len(list(daily_dir.glob("*.md")))

        # 归档统计
        archive_dir = self.base_dir / ARCHIVE_DIR
        stats["archive_files"] = len(list(archive_dir.glob("*.md")))

        return stats


# ============== 单例 ==============

_instance: Optional[MemoryStore] = None

def get_memory_store(base_dir: Optional[Path] = None) -> MemoryStore:
    global _instance
    if _instance is None:
        _instance = MemoryStore(base_dir)
    return _instance
