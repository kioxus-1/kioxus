"""
Kioxus Core v2 — 会话管理
对话历史、checkpoint、会话恢复
"""

import json
import time
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class Turn:
    """一轮对话"""
    role: str                   # "user" / "assistant"
    content: str                # 消息内容
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)  # 意图、工具调用等

    def to_dict(self) -> dict:
        """to_dict"""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Turn":
        """from_dict"""
        return cls(**d)


@dataclass
class Checkpoint:
    """会话存档点"""
    checkpoint_id: str
    session_id: str
    turn_count: int
    turns: List[Turn]
    created_at: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """to_dict"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "turns": [t.to_dict() for t in self.turns],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class Session:
    """单个会话"""

    def __init__(self, session_id: str, max_history: int = 50):
        """__init__"""
        self.session_id = session_id
        self.turns: List[Turn] = []
        self.max_history = max_history
        self.created_at = time.time()
        self.last_active = time.time()
        self.metadata: Dict = {}

    @property
    def turn_count(self) -> int:
        """turn_count"""
        return len(self.turns)

    def add_turn(self, role: str, content: str, metadata: Dict = None) -> Turn:
        """添加一轮对话"""
        turn = Turn(role=role, content=content, metadata=metadata or {})
        self.turns.append(turn)
        self.last_active = time.time()

        # 超过上限时裁剪（保留最近的）
        if len(self.turns) > self.max_history:
            self.turns = self.turns[-self.max_history:]

        return turn

    def get_recent(self, n: int = 10) -> List[Turn]:
        """获取最近n轮对话"""
        return self.turns[-n:]

    def get_messages(self, n: int = 10) -> List[Dict]:
        """获取最近n轮，格式化为LLM消息格式"""
        recent = self.get_recent(n)
        return [{"role": t.role, "content": t.content} for t in recent]

    def clear(self):
        """清空会话历史"""
        self.turns.clear()
        self.last_active = time.time()

    def get_history_text(self) -> str:
        """将对话历史格式化为可读文本"""
        if not self.turns:
            return ""
        lines = []
        for t in self.turns:
            role = "用户" if t.role == "user" else "Kioxus"
            lines.append(f"{role}: {t.content}")
        return "\n".join(lines)


class SessionManager:
    """会话管理器"""

    def __init__(self, storage_dir: Path = None, max_history: int = 50):
        """__init__"""
        self.storage_dir = storage_dir or Path("data/sessions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history
        self._sessions: Dict[str, Session] = {}
        self._current: Optional[Session] = None

    @property
    def current(self) -> Optional[Session]:
        """current"""
        return self._current

    @property
    def current_session(self) -> Optional[Session]:
        """兼容engine.py的访问方式"""
        return self._current

    def start_session(self, session_id: str = None) -> Session:
        """开始新会话"""
        if session_id is None:
            session_id = f"session_{int(time.time())}"

        session = Session(session_id, self.max_history)
        self._sessions[session_id] = session
        self._current = session
        return session

    def get_or_create(self, session_id: str) -> Session:
        """获取已有会话或创建新会话（优先从文件加载）"""
        if session_id in self._sessions:
            self._current = self._sessions[session_id]
            return self._current
        # 尝试从文件加载
        if self.load_session(session_id):
            return self._current
        return self.start_session(session_id)

    def add_turn(self, role: str, content: str, metadata: Dict = None):
        """向当前会话添加一轮对话"""
        if self._current is None:
            self.start_session()
        self._current.add_turn(role, content, metadata)

    def get_recent_messages(self, n: int = 10) -> List[Dict]:
        """获取当前会话最近n轮的LLM格式消息"""
        if self._current is None:
            return []
        return self._current.get_messages(n)

    # ========== Checkpoint ==========

    def checkpoint(self, session_id: str = None) -> Checkpoint:
        """保存当前会话的存档点"""
        session = self._sessions.get(session_id) if session_id else self._current
        if session is None:
            raise ValueError("No active session to checkpoint")

        cp = Checkpoint(
            checkpoint_id=f"cp_{int(time.time())}",
            session_id=session.session_id,
            turn_count=session.turn_count,
            turns=list(session.turns),
            metadata={"created_at": session.created_at},
        )

        # 写入文件
        cp_path = self.storage_dir / f"{cp.checkpoint_id}.json"
        cp_path.write_text(json.dumps(cp.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

        return cp

    def restore(self, checkpoint_id: str) -> bool:
        """从存档点恢复会话"""
        cp_path = self.storage_dir / f"{checkpoint_id}.json"
        if not cp_path.exists():
            return False

        try:
            data = json.loads(cp_path.read_text(encoding="utf-8"))
            session = Session(data["session_id"], self.max_history)
            session.turns = [Turn.from_dict(t) for t in data.get("turns", [])]
            session.created_at = data.get("created_at", time.time())
            self._sessions[session.session_id] = session
            self._current = session
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def list_checkpoints(self) -> List[Dict]:
        """列出所有存档点"""
        cps = []
        for f in self.storage_dir.glob("cp_*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cps.append({
                    "checkpoint_id": data["checkpoint_id"],
                    "session_id": data["session_id"],
                    "turn_count": data["turn_count"],
                    "created_at": data["created_at"],
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sorted(cps, key=lambda x: x["created_at"], reverse=True)

    # ========== 持久化 ==========

    def save_session(self, session_id: str = None):
        """保存会话到文件"""
        session = self._sessions.get(session_id) if session_id else self._current
        if session is None:
            return

        path = self.storage_dir / f"{session.session_id}.json"
        data = {
            "session_id": session.session_id,
            "turns": [t.to_dict() for t in session.turns],
            "created_at": session.created_at,
            "last_active": session.last_active,
            "metadata": session.metadata,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_session(self, session_id: str) -> bool:
        """从文件加载会话"""
        path = self.storage_dir / f"{session_id}.json"
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            session = Session(data["session_id"], self.max_history)
            session.turns = [Turn.from_dict(t) for t in data.get("turns", [])]
            session.created_at = data.get("created_at", time.time())
            session.last_active = data.get("last_active", time.time())
            session.metadata = data.get("metadata", {})
            self._sessions[session.session_id] = session
            self._current = session
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def flush_to_today(self, today_path: Path = None) -> bool:
        """
        将当前上下文复制到 today.md，然后清空上下文
        每6小时调用一次（0/6/12/18点）
        """
        if self._current is None or self._current.turn_count == 0:
            return False

        # 读取现有 today.md 内容
        if today_path is None:
            # storage_dir = data/sessions, 上两级到 kioxus根目录
            today_path = self.storage_dir.parent.parent / "memory_v2" / "data" / "short-term" / "today.md"

        existing = ""
        if today_path.exists():
            existing = today_path.read_text(encoding="utf-8")

        # 格式化当前对话
        now = time.strftime("%H:%M")
        history = self._current.get_history_text()
        if not history:
            return False

        # 追加到 today.md
        section = f"\n\n## [{now}] 上下文快照\n\n{history}\n"

        # 如果文件开头是测试数据，先清空
        if "测试记忆条目" in existing:
            existing = "# 今日记忆\n"

        new_content = existing.rstrip() + section
        today_path.parent.mkdir(parents=True, exist_ok=True)
        today_path.write_text(new_content, encoding="utf-8")

        # 清空上下文
        self._current.clear()
        self.save_session()

        return True

    def compress_history(self, llm_call, n_recent: int = 5) -> str:
        """
        压缩历史对话
        保留最近n_recent轮完整，更早的压缩为摘要
        llm_call: callable(prompt: str) -> str
        """
        if self._current is None or self._current.turn_count <= n_recent:
            return ""

        # 取出需要压缩的部分
        old_turns = self._current.turns[:-n_recent]
        if not old_turns:
            return ""

        # 构建压缩提示
        history_text = "\n".join(
            f"{'用户' if t.role == 'user' else '助手'}: {t.content}"
            for t in old_turns
        )
        prompt = f"请将以下对话历史压缩为简短摘要，保留关键信息：\n\n{history_text}"

        try:
            summary = llm_call(prompt)
            # 替换旧对话为摘要
            summary_turn = Turn(
                role="system",
                content=f"[历史摘要] {summary}",
                metadata={"type": "compressed_summary", "original_count": len(old_turns)},
            )
            self._current.turns = [summary_turn] + self._current.turns[-n_recent:]
            return summary
        except Exception as e:
            return f"压缩失败: {e}"


# ============== 单例 ==============

_instance: Optional[SessionManager] = None


def get_session_manager(storage_dir: Path = None) -> SessionManager:
    """get_session_manager"""
    global _instance
    if _instance is None:
        _instance = SessionManager(storage_dir)
    return _instance
