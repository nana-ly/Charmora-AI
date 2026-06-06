import sqlite3

import pytest

from agent.memory import ConversationState, InMemoryConversationStore
from schemas.chat import ChatMessage


def test_conversation_state_defaults_version_for_legacy_json():
    state = ConversationState.model_validate_json(
        '{"session_id":"legacy-session","messages":[]}'
    )

    assert state.version == 0
    assert '"version":0' in state.model_dump_json()


def test_in_memory_update_increments_version_and_supports_in_place_mutator():
    store = InMemoryConversationStore()

    updated = store.update(
        "memory-session",
        lambda state: state.messages.append(ChatMessage(role="user", content="你好")),
    )

    assert updated.version == 1
    assert updated.messages[0].content == "你好"
    assert store.get_or_create("memory-session").version == 1


def test_in_memory_update_owns_version_when_mutator_returns_same_object():
    store = InMemoryConversationStore()

    def mutate(state: ConversationState) -> ConversationState:
        state.purchase_need = "推荐手机"
        state.version = 99
        return state

    updated = store.update("memory-version-owner", mutate)

    assert updated.version == 1
    assert updated.purchase_need == "推荐手机"


def test_in_memory_save_increments_version():
    store = InMemoryConversationStore()
    state = store.get_or_create("memory-save")
    state.purchase_need = "推荐手机"

    store.save(state)

    assert store.get_or_create("memory-save").version == 1


def test_sqlite_initializes_version_column_for_existing_table(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE conversation_states (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            "INSERT INTO conversation_states(session_id, state_json) VALUES (?, ?)",
            ("legacy", '{"session_id":"legacy","messages":[]}'),
        )

    store = SQLiteConversationStore(db_path)
    loaded = store.get_or_create("legacy")

    assert loaded.version == 0
    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(conversation_states)")
        }
    assert "version" in columns


def test_sqlite_save_increments_and_persists_version(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    store = SQLiteConversationStore(tmp_path / "save.sqlite3")
    state = store.get_or_create("sqlite-save")
    state.purchase_need = "推荐手机"

    store.save(state)
    first = store.get_or_create("sqlite-save")
    first_version = first.version
    store.save(first)
    second = store.get_or_create("sqlite-save")

    assert first_version == 1
    assert second.version == 2


def test_sqlite_update_increments_version_and_supports_returned_state(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    store = SQLiteConversationStore(tmp_path / "update.sqlite3")

    updated = store.update(
        "sqlite-update",
        lambda state: state.model_copy(update={"purchase_need": "推荐咖啡"}),
    )

    assert updated.version == 1
    assert updated.purchase_need == "推荐咖啡"
    assert store.get_or_create("sqlite-update").version == 1


def test_sqlite_update_does_not_commit_when_mutator_raises(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")

    def fail_mutator(state: ConversationState):
        state.purchase_need = "这次变更不应提交"
        raise RuntimeError("mutator failed")

    with pytest.raises(RuntimeError, match="mutator failed"):
        store.update("rollback-session", fail_mutator)

    saved = store.get_or_create("rollback-session")
    assert saved.version == 0
    assert saved.purchase_need is None
    assert saved.messages == []


def test_sqlite_update_retries_after_version_conflict(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    db_path = tmp_path / "conversations.sqlite3"
    store_a = SQLiteConversationStore(db_path, update_retries=2)
    store_b = SQLiteConversationStore(db_path, update_retries=2)
    calls = {"count": 0}

    def mutator_a(state: ConversationState):
        calls["count"] += 1
        if calls["count"] == 1:
            store_b.update(
                "conflict-session",
                lambda other: setattr(other, "purchase_need", "B 先写入") or other,
            )
        state.preferences["from_a"] = True
        return state

    updated = store_a.update("conflict-session", mutator_a)

    assert calls["count"] == 2
    assert updated.version == 2
    assert updated.purchase_need == "B 先写入"
    assert updated.preferences["from_a"] is True

    saved = store_a.get_or_create("conflict-session")
    assert saved.version == 2
    assert saved.purchase_need == "B 先写入"
    assert saved.preferences["from_a"] is True


def test_sqlite_update_supports_in_place_mutator(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    store = SQLiteConversationStore(tmp_path / "update-in-place.sqlite3")

    updated = store.update(
        "sqlite-update-in-place",
        lambda state: state.messages.append(ChatMessage(role="user", content="你好")),
    )

    assert updated.version == 1
    assert updated.messages[0].content == "你好"
