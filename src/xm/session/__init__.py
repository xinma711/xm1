"""Session storage with SQLite"""

import json
import sqlite3
import uuid
from datetime import datetime

from xm.config import DB_FILE, ensure_config_dir


class Session:
    def __init__(self, session_id: str | None = None):
        ensure_config_dir()
        self.conn = sqlite3.connect(str(DB_FILE))
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self.id = session_id or self._create_session()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                tool_calls TEXT,
                tool_call_id TEXT,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
        """)
        self.conn.commit()

    def _create_session(self) -> str:
        sid = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (sid, now, now),
        )
        self.conn.commit()
        return sid

    def add_message(
        self,
        role: str,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
    ):
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, tool_call_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                self.id,
                role,
                content,
                json.dumps(tool_calls) if tool_calls else None,
                tool_call_id,
                now,
            ),
        )
        self.conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, self.id)
        )
        self.conn.commit()

    def get_messages(self) -> list[dict]:
        """Get messages in LLM API format."""
        rows = self.conn.execute(
            "SELECT role, content, tool_calls, tool_call_id FROM messages "
            "WHERE session_id = ? ORDER BY id",
            (self.id,),
        ).fetchall()
        messages = []
        for row in rows:
            msg = {"role": row["role"]}
            if row["content"]:
                msg["content"] = row["content"]
            if row["tool_calls"]:
                msg["tool_calls"] = json.loads(row["tool_calls"])
            if row["tool_call_id"]:
                msg["tool_call_id"] = row["tool_call_id"]
            messages.append(msg)
        return messages

    def set_title(self, title: str):
        self.conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?", (title, self.id)
        )
        self.conn.commit()

    def get_title(self) -> str | None:
        row = self.conn.execute(
            "SELECT title FROM sessions WHERE id = ?", (self.id,)
        ).fetchone()
        return row["title"] if row else None

    def close(self):
        self.conn.close()


def list_sessions(limit: int = 20) -> list[dict]:
    """List recent sessions."""
    ensure_config_dir()
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    # Ensure tables exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            created_at TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        );
    """)
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM sessions "
        "ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
