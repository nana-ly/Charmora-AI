import sqlite3

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


def test_sqlite_update_supports_in_place_mutator(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    store = SQLiteConversationStore(tmp_path / "update-in-place.sqlite3")

    updated = store.update(
        "sqlite-update-in-place",
        lambda state: state.messages.append(ChatMessage(role="user", content="你好")),
    )

    assert updated.version == 1
    assert updated.messages[0].content == "你好"
