"""SQLite 会话状态存储。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from collections.abc import Callable

from agent.memory import ConversationState


class ConversationStoreConflictError(RuntimeError):
    """SQLite 乐观更新超过重试次数后抛出的明确冲突错误。"""


class SQLiteConversationStore:
    """把完整 ConversationState JSON 持久化到本地 SQLite。"""

    def __init__(self, path: str | Path, update_retries: int = 3) -> None:
        self.path = Path(path)
        self.update_retries = update_retries
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get_or_create(self, session_id: str) -> ConversationState:
        """读取会话；不存在时返回空状态。"""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT state_json, version FROM conversation_states WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return ConversationState(session_id=session_id)
        return _state_from_row(row[0], row[1])

    def save(self, state: ConversationState) -> None:
        """使用 UPSERT 保存当前会话状态。"""
        state.version += 1
        payload = state.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_states(session_id, state_json, version, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    version = excluded.version,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (state.session_id, payload, state.version),
            )

    def update(
        self,
        session_id: str,
        mutator: Callable[[ConversationState], ConversationState | None],
    ) -> ConversationState:
        """用 version 条件更新实现有限重试的乐观并发。"""
        attempts = max(self.update_retries, 1)
        for _ in range(attempts):
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT state_json, version FROM conversation_states WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                current = (
                    ConversationState(session_id=session_id)
                    if row is None
                    else _state_from_row(row[0], row[1])
                )
                current_version = current.version
                mutated = mutator(current)
                next_state = current if mutated is None else mutated
                next_state.version = current_version + 1
                payload = next_state.model_dump_json()

                if row is None:
                    try:
                        connection.execute(
                            """
                            INSERT INTO conversation_states(
                                session_id,
                                state_json,
                                version,
                                updated_at
                            )
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                            """,
                            (session_id, payload, next_state.version),
                        )
                    except sqlite3.IntegrityError:
                        continue
                    return next_state

                cursor = connection.execute(
                    """
                    UPDATE conversation_states
                    SET state_json = ?, version = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ? AND version = ?
                    """,
                    (payload, next_state.version, session_id, current_version),
                )
                if cursor.rowcount:
                    return next_state
        raise ConversationStoreConflictError(
            f"conversation state update conflict after {attempts} attempts"
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_states (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(conversation_states)")
            }
            if "version" not in columns:
                # 兼容旧 SQLite 文件：新增列即可，旧 JSON 由 Pydantic 默认 version=0 承接。
                connection.execute(
                    "ALTER TABLE conversation_states ADD COLUMN version INTEGER NOT NULL DEFAULT 0"
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=5)


def _state_from_row(state_json: str, version: int) -> ConversationState:
    state = ConversationState.model_validate_json(state_json)
    state.version = int(version)
    return state
