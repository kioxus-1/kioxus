"""
Kioxus Memory System v2 — Memory Janitor
记忆维护：Flush、结算、压缩、归档、战略性遗忘
代码管逻辑，LLM管语义
"""

import json
import re
import time
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from .memory import MemoryStore, MemoryEntry, parse_frontmatter, build_frontmatter, get_memory_store
from .tags import TagDictionary, get_tag_dictionary

# ============== 配置 ==============

# 战略性遗忘阈值
FORGET_THRESHOLDS = {
    "P3": 30,    # P3 超过30天物理删除
    "P2": 180,   # P2 超过180天未检索物理删除
    "P1": 365,   # P1 超过365天移入归档
    "P0": None,  # P0 永不销毁
}

# 反思层行数阈值
REFLECTION_LINE_THRESHOLD = 200

# ============== Flush Agent 输出 Schema ==============

FLUSH_SCHEMA = {
    "required": ["date", "priority_summary", "unfinished_tasks"],
    "properties": {
        "date": {"type": "string"},
        "priority_summary": {
            "type": "object",
            "required": ["P0", "P1", "P2"],
            "properties": {
                "P0": {"type": "array"},
                "P1": {"type": "array"},
                "P2": {"type": "array"},
            },
        },
        "unfinished_tasks": {"type": "array"},
        "atmosphere": {"type": "string"},
    },
}


def validate_flush_output(data: dict) -> Tuple[bool, List[str]]:
    """校验 Flush Agent 的输出"""
    errors = []

    if not isinstance(data, dict):
        return False, ["Output is not a dict"]

    for field in FLUSH_SCHEMA["required"]:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "priority_summary" in data:
        ps = data["priority_summary"]
        for level in ["P0", "P1", "P2"]:
            if level not in ps:
                errors.append(f"Missing priority level: {level}")
            elif not isinstance(ps[level], list):
                errors.append(f"P{level} must be a list")
            else:
                for i, item in enumerate(ps[level]):
                    if not isinstance(item, dict):
                        errors.append(f"P{level}[{i}] must be a dict")
                    elif "fact" not in item:
                        errors.append(f"P{level}[{i}] missing 'fact'")

    return len(errors) == 0, errors


# ============== 文件锁 ==============

class FileLock:
    """轻量文件锁"""

    def __init__(self, path: Path, timeout: int = 60):
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.timeout = timeout

    def acquire(self) -> bool:
        """获取锁"""
        if self.lock_path.exists():
            # 检查是否超时
            try:
                data = json.loads(self.lock_path.read_text(encoding="utf-8"))
                if time.time() - data.get("timestamp", 0) > self.timeout:
                    self.release()  # 超时释放
                else:
                    return False  # 锁被持有
            except Exception:
                self.release()  # 损坏的锁文件，直接释放

        self.lock_path.write_text(
            json.dumps({"pid": "janitor", "timestamp": time.time()}),
            encoding="utf-8",
        )
        return True

    def release(self):
        """释放锁"""
        if self.lock_path.exists():
            self.lock_path.unlink()

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock: {self.lock_path}")
        return self

    def __exit__(self, *args):
        self.release()


# ============== Memory Janitor ==============

class MemoryJanitor:
    """
    记忆维护器 — 定期执行记忆管理工作
    代码层负责逻辑和计算，LLM负责文本压缩
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        tags: Optional[TagDictionary] = None,
    ):
        self.store = store or get_memory_store()
        self.tags = tags or get_tag_dictionary()

    # ========== Memory Flush ==========

    def flush_today(self, flush_output: dict) -> Dict:
        """
        执行 Memory Flush
        输入: Flush Agent 的结构化输出
        输出: 执行结果
        """
        # 校验输出
        valid, errors = validate_flush_output(flush_output)
        if not valid:
            return {
                "action": "rejected",
                "errors": errors,
                "message": "Flush output validation failed, today.md preserved",
            }

        # 读取 today.md 作为备份
        today_content = self.store.read_today()
        if not today_content.strip():
            return {"action": "skipped", "message": "today.md is empty"}

        # 写入 today_pending.json（缓冲区）
        pending_path = self.store.base_dir / "short-term" / "today_pending.json"
        pending_path.write_text(
            json.dumps(flush_output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 重命名 today.md 为备份
        today_path = self.store.base_dir / "short-term" / "today.md"
        backup_path = self.store.base_dir / "short-term" / "today_backup.md"
        if today_path.exists():
            shutil.copy2(str(today_path), str(backup_path))

        return {
            "action": "flushed",
            "pending_path": str(pending_path),
            "backup_path": str(backup_path),
            "p0_count": len(flush_output.get("priority_summary", {}).get("P0", [])),
            "p1_count": len(flush_output.get("priority_summary", {}).get("P1", [])),
            "p2_count": len(flush_output.get("priority_summary", {}).get("P2", [])),
        }

    # ========== 每日结算 ==========

    def settle_daily(self, date_str: str = None) -> Dict:
        """
        每日结算：将 flush 输出写入 daily/，清空 today.md
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # 读取 pending
        pending_path = self.store.base_dir / "short-term" / "today_pending.json"
        if not pending_path.exists():
            return {"action": "skipped", "message": "No pending flush output"}

        try:
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
        except Exception as e:
            return {"action": "error", "message": f"Failed to read pending: {e}"}

        # 检查是否有新消息（today_new.md）
        new_path = self.store.base_dir / "short-term" / "today_new.md"
        new_content = ""
        if new_path.exists():
            new_content = new_path.read_text(encoding="utf-8")

        # 生成 daily 文件
        daily_content = self._build_daily_content(date_str, pending, new_content)
        self.store.write_daily(date_str, daily_content)

        # 清空工作区
        self.store.clear_today()
        if pending_path.exists():
            pending_path.unlink()
        if new_path.exists():
            new_path.unlink()

        # 删除备份
        backup_path = self.store.base_dir / "short-term" / "today_backup.md"
        if backup_path.exists():
            backup_path.unlink()

        # 更新 overview.md
        self._update_overview()

        return {
            "action": "settled",
            "date": date_str,
            "daily_file": f"daily/{date_str}.md",
        }

    def monthly_maintenance(self) -> Dict:
        """
        每月维护：战略性遗忘 + 标签报告 + overview更新
        建议每月1号调用
        """
        result = {
            "forget": {"deleted": [], "archived": []},
            "tag_report": {},
            "bloat_check": [],
        }

        # 1. 战略性遗忘
        # 读取所有reflection模块
        all_entries = []
        for module in self.store.list_reflection_modules():
            content = self.store.read_reflection(module)
            if content:
                # 简化：创建一个虚拟entry用于遗忘检查
                # 实际应该解析frontmatter获取真实entry
                pass

        # 2. 生成标签报告
        result["tag_report"] = self.generate_tag_report()

        # 3. 检查反思膨胀
        result["bloat_check"] = self.check_reflection_bloat()

        # 4. 更新overview
        self._update_overview()

        return result

    def _build_daily_content(self, date_str: str, pending: dict, new_content: str) -> str:
        """构建 daily 文件内容"""
        lines = [f"# {date_str} 记忆结算\n"]

        ps = pending.get("priority_summary", {})
        for level in ["P0", "P1", "P2"]:
            items = ps.get(level, [])
            if items:
                lines.append(f"\n## {level}\n")
                for item in items:
                    fact = item.get("fact", "")
                    action = item.get("action", "")
                    tags = item.get("tags", [])
                    lines.append(f"- **{fact}**")
                    if action:
                        lines.append(f"  - 行动: {action}")
                    if tags:
                        lines.append(f"  - 标签: {', '.join(tags)}")

        unfinished = pending.get("unfinished_tasks", [])
        if unfinished:
            lines.append("\n## 未完成任务\n")
            for task in unfinished:
                lines.append(f"- {task}")

        atmosphere = pending.get("atmosphere", "")
        if atmosphere:
            lines.append(f"\n## 氛围\n{atmosphere}")

        if new_content and new_content.strip():
            lines.append(f"\n## 安全窗口新消息\n{new_content}")

        return "\n".join(lines)

    # ========== 压缩评分 ==========

    def calculate_score(self, entry: MemoryEntry) -> float:
        """
        代码层计算记忆得分（不让LLM算数）
        检索频率 0.30 + 时效性 0.25 + 用户强化 0.25 + 关联密度 0.20
        """
        # 检索频率（上限10次封顶）
        recall_score = min(entry.recall_count / 10, 1.0)

        # 时效性（30天半衰期）
        age_days = (time.time() - entry.created_at) / 86400
        freshness_score = max(1 - age_days / 30, 0)

        # 用户强化
        user_score = 1.0 if entry.source_type == "user" else 0.0

        # 关联密度（标签数近似）
        density_score = min(len(entry.tags) / 5, 1.0)

        return (
            recall_score * 0.30
            + freshness_score * 0.25
            + user_score * 0.25
            + density_score * 0.20
        )

    def rank_entries(self, entries: List[MemoryEntry]) -> List[Tuple[MemoryEntry, float]]:
        """对记忆条目评分排序"""
        scored = [(entry, self.calculate_score(entry)) for entry in entries]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ========== 压缩校验 ==========

    def validate_compression(self, original: str, compressed: str) -> Tuple[bool, Dict]:
        """
        代码层硬性校验压缩结果
        返回: (passed, report)
        """
        report = {}

        # 1. 提取 action 字段
        original_actions = self._extract_actions(original)
        compressed_actions = self._extract_actions(compressed)
        actions_preserved = len(compressed_actions) >= len(original_actions)
        report["actions"] = {
            "original": len(original_actions),
            "compressed": len(compressed_actions),
            "preserved": actions_preserved,
        }

        # 2. P0/P1 必须保留
        original_p01 = self._extract_by_priority(original, ["P0", "P1"])
        compressed_p01 = self._extract_by_priority(compressed, ["P0", "P1"])
        p01_preserved = len(compressed_p01) >= len(original_p01)
        report["p0_p1"] = {
            "original": len(original_p01),
            "compressed": len(compressed_p01),
            "preserved": p01_preserved,
        }

        # 3. 标签覆盖率 > 90%
        original_tags = self._extract_tags(original)
        compressed_tags = self._extract_tags(compressed)
        if original_tags:
            coverage = len(compressed_tags & original_tags) / len(original_tags)
        else:
            coverage = 1.0
        tags_ok = coverage > 0.9
        report["tags"] = {
            "original_count": len(original_tags),
            "compressed_count": len(compressed_tags),
            "coverage": round(coverage, 2),
            "ok": tags_ok,
        }

        passed = actions_preserved and p01_preserved and tags_ok
        report["passed"] = passed

        return passed, report

    def _extract_actions(self, text: str) -> List[str]:
        """提取行动字段"""
        actions = []
        for line in text.split("\n"):
            line = line.strip()
            if "[行动]" in line or "行动:" in line:
                actions.append(line)
        return actions

    def _extract_by_priority(self, text: str, priorities: List[str]) -> List[str]:
        """按优先级提取"""
        results = []
        for line in text.split("\n"):
            for p in priorities:
                if p in line:
                    results.append(line)
                    break
        return results

    def _extract_tags(self, text: str) -> set:
        """提取标签"""
        tags = set()
        for match in re.finditer(r'#(\w+)', text):
            tags.add(match.group(1))
        return tags

    # ========== 战略性遗忘 ==========

    def forget_expired(self, entries: List[MemoryEntry]) -> Dict:
        """
        战略性遗忘 — P3超30天删除，P2超180天未检索删除
        返回: {deleted: [...], archived: [...]}
        """
        now = time.time()
        deleted = []
        archived = []

        for entry in entries:
            age_days = (now - entry.created_at) / 86400
            threshold = FORGET_THRESHOLDS.get(entry.priority)

            if threshold is None:
                continue  # P0 永不销毁

            # P2 特殊条件：180天且 recall_count == 0
            if entry.priority == "P2":
                if age_days > 180 and entry.recall_count == 0:
                    deleted.append(entry)
                    continue

            # P3：30天物理删除
            if entry.priority == "P3" and age_days > threshold:
                deleted.append(entry)
                continue

            # P1：365天移入归档
            if entry.priority == "P1" and age_days > 365:
                archived.append(entry)
                continue

        return {"deleted": deleted, "archived": archived}

    # ========== overview.md ==========

    def _update_overview(self):
        """更新 overview.md（≤10行）"""
        stats = self.store.get_memory_stats()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            f"# 记忆概览 (更新于 {now})",
            f"",
            f"- 核心层: {stats['core_lines']} 行",
            f"- 今日: {stats['today_lines']} 行",
            f"- 反思层: {len(stats['reflection_modules'])} 个模块",
            f"- 每日日志: {stats['daily_files']} 份",
            f"- 归档: {stats['archive_files']} 份",
        ]

        # 反思模块详情
        if stats["reflection_modules"]:
            module_info = ", ".join(f"{m}({l}行)" for m, l in stats["reflection_modules"].items())
            lines.append(f"- 反思模块: {module_info}")

        self.store.write_overview("\n".join(lines))

    # ========== 反思膨胀控制 ==========

    def check_reflection_bloat(self) -> List[Dict]:
        """检查反思层膨胀"""
        bloated = []
        for module in self.store.list_reflection_modules():
            lines = self.store.count_lines("reflection", module)
            if lines >= REFLECTION_LINE_THRESHOLD:
                bloated.append({
                    "module": module,
                    "lines": lines,
                    "threshold": REFLECTION_LINE_THRESHOLD,
                    "action": "compress_needed",
                })
        return bloated

    # ========== 标签维护 ==========

    def generate_tag_report(self) -> Dict:
        """生成标签膨胀报告"""
        return self.tags.get_bloat_report()

    # ========== 健康度报告 ==========

    def health_report(self) -> Dict:
        """生成健康度报告"""
        stats = self.store.get_memory_stats()
        tag_report = self.tags.get_bloat_report()
        bloat = self.check_reflection_bloat()

        return {
            "memory_stats": stats,
            "tag_stats": {
                "total": tag_report["total_tags"],
                "active": tag_report["active"],
                "never_used": len(tag_report["never_used"]),
            },
            "reflection_bloat": bloat,
            "overall_health": "good" if not bloat else "needs_attention",
        }


# ============== 单例 ==============

_instance: Optional[MemoryJanitor] = None

def get_janitor(
    store: Optional[MemoryStore] = None,
    tags: Optional[TagDictionary] = None,
) -> MemoryJanitor:
    global _instance
    if _instance is None:
        _instance = MemoryJanitor(store, tags)
    return _instance
