from __future__ import annotations

from copy import deepcopy

import pytest

from agent.graph.runner import LangGraphAgentRunner
from agent.memory import ConversationState, InMemoryConversationStore, SessionLockManager
from agent.tools import RecommendationTool
from agent.understanding import UserIntent, UserUnderstanding
from schemas.product import ProductCard


class TrackingVersionedStore:
    """带版本 store fake：事务路径里如果调用 save() 就让测试失败。"""

    def __init__(self):
        self.state = ConversationState(session_id="transaction-session")
        self.update_calls = 0
        self.save_calls = 0

    def get_or_create(self, session_id: str) -> ConversationState:
        if self.state.session_id != session_id:
            self.state = ConversationState(session_id=session_id)
        return deepcopy(self.state)

    def save(self, state: ConversationState) -> None:
        self.save_calls += 1
        raise AssertionError("transactional runner must not call save()")

    def update(self, session_id: str, mutator):
        self.update_calls += 1
        current = self.get_or_create(session_id)
        mutated = mutator(current)
        next_state = current if mutated is None else mutated
        next_state.version = current.version + 1
        self.state = deepcopy(next_state)
        return deepcopy(next_state)


class StaticUnderstandingService:
    """固定返回推荐意图，避免测试依赖 LLM。"""

    def understand(self, *, message, conversation):
        return UserUnderstanding(
            intent=UserIntent.RECOMMEND,
            confidence=0.9,
            purchase_need=message,
            preference_updates={
                "target_category": "手机",
                "category": "数码电子",
                "canonical_target_key": "phone",
            },
        )


def one_item_recommendation(query: str, top_k: int = 3, negative_filters=None):
    return {
        "query": query,
        "filters": {
            "category": "数码电子",
            "max_price": None,
            "brand": None,
            "keywords": ["手机"],
        },
        "result_count": 1,
        "items": [
            ProductCard(
                product_id="p_tx_phone",
                title="事务测试手机",
                brand="TestPhone",
                price=2999,
                reason="符合事务测试需求",
                evidence="transaction-test",
            )
        ],
    }


def test_langgraph_runner_uses_store_update_and_does_not_call_save():
    store = TrackingVersionedStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=one_item_recommendation),
        understanding_service=StaticUnderstandingService(),
        session_lock_manager=SessionLockManager(),
    )

    response = runner.run("transaction-session", "推荐手机")

    assert store.update_calls == 1
    assert store.save_calls == 0
    assert response.session_id == "transaction-session"
    assert response.items[0].product_id == "p_tx_phone"
    assert store.state.version == 1
    assert [message.role for message in store.state.messages] == ["user", "assistant"]
    assert store.state.messages[0].content == "推荐手机"
    assert store.state.last_successful_items[0].product_id == "p_tx_phone"


class FailingUnderstandingService:
    """理解阶段抛错，用于验证半成品状态不会提交。"""

    def understand(self, *, message, conversation):
        raise RuntimeError("understanding failed")


def test_langgraph_runner_does_not_commit_partial_state_when_graph_fails():
    store = TrackingVersionedStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=one_item_recommendation),
        understanding_service=FailingUnderstandingService(),
        session_lock_manager=SessionLockManager(),
    )

    with pytest.raises(RuntimeError, match="understanding failed"):
        runner.run("transaction-session", "推荐手机")

    assert store.update_calls == 1
    assert store.save_calls == 0
    assert store.state.version == 0
    assert store.state.messages == []
    assert store.state.last_successful_items == []


def test_langgraph_runner_with_memory_store_rolls_back_partial_state_when_graph_fails():
    store = InMemoryConversationStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=one_item_recommendation),
        understanding_service=FailingUnderstandingService(),
        session_lock_manager=SessionLockManager(),
    )

    with pytest.raises(RuntimeError, match="understanding failed"):
        runner.run("memory-rollback-session", "推荐手机")

    saved = store.get_or_create("memory-rollback-session")
    assert saved.version == 0
    assert saved.messages == []
    assert saved.last_successful_items == []


def test_langgraph_runner_with_sqlite_store_persists_full_turn_transaction(tmp_path):
    from agent.sqlite_memory import SQLiteConversationStore

    store = SQLiteConversationStore(tmp_path / "chat.sqlite3")
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=one_item_recommendation),
        understanding_service=StaticUnderstandingService(),
        session_lock_manager=SessionLockManager(),
    )

    response = runner.run("sqlite-transaction-session", "推荐手机")

    saved = store.get_or_create("sqlite-transaction-session")
    assert response.items[0].product_id == "p_tx_phone"
    assert saved.version == 1
    assert [message.role for message in saved.messages] == ["user", "assistant"]
    assert saved.purchase_need == "推荐手机"
    assert saved.preferences["canonical_target_key"] == "phone"
    assert saved.last_successful_items[0].product_id == "p_tx_phone"
