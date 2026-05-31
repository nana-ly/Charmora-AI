"""SQLite 会话状态存储。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from agent.memory import ConversationState


class SQLiteConversationStore:
    """把完整 ConversationState JSON 持久化到本地 SQLite。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get_or_create(self, session_id: str) -> ConversationState:
        """读取会话；不存在时返回空状态。"""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM conversation_states WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return ConversationState(session_id=session_id)
        return ConversationState.model_validate_json(row[0])

    def save(self, state: ConversationState) -> None:
        """使用 UPSERT 保存当前会话状态。"""
        payload = state.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_states(session_id, state_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (state.session_id, payload),
            )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_states (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)
