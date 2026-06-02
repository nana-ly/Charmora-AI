from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from agent.memory import ConversationState, InMemoryConversationStore, SessionLockManager
from agent.tools import RecommendationTool
from agent.understanding import UserIntent, UserUnderstanding
from schemas.chat import ChatMessage
from schemas.product import ProductCard


class CopyOnReadConversationStore:
    """模拟 SQLite 这类读写分离存储，暴露并发覆盖风险。"""

    def __init__(self):
        self._states: dict[str, ConversationState] = {}

    def get_or_create(self, session_id: str) -> ConversationState:
        if session_id not in self._states:
            self._states[session_id] = ConversationState(session_id=session_id)
        return deepcopy(self._states[session_id])

    def save(self, state: ConversationState) -> None:
        self._states[state.session_id] = deepcopy(state)

    def update(self, session_id: str, mutator):
        current = self.get_or_create(session_id)
        current_version = current.version
        mutated = mutator(current)
        next_state = current if mutated is None else mutated
        next_state.version = current_version + 1
        self._states[session_id] = deepcopy(next_state)
        return deepcopy(next_state)


class NonVersionedCopyOnReadConversationStore:
    """旧 get/save store，用于验证 fallback path 仍可能丢写。"""

    def __init__(self):
        self._states: dict[str, ConversationState] = {}

    def get_or_create(self, session_id: str) -> ConversationState:
        if session_id not in self._states:
            self._states[session_id] = ConversationState(session_id=session_id)
        return deepcopy(self._states[session_id])

    def save(self, state: ConversationState) -> None:
        self._states[state.session_id] = deepcopy(state)


class EchoGraph:
    """用轻量图替代 LangGraph，专注验证 Runner 的锁和事务边界。"""

    def __init__(self, store, delay_seconds: float = 0.02):
        self.store = store
        self.delay_seconds = delay_seconds

    def invoke(self, state):
        conversation = state.get("conversation") or self.store.get_or_create(
            state["session_id"]
        )
        conversation.messages.append(ChatMessage(role="user", content=state["message"]))
        time.sleep(self.delay_seconds)
        conversation.messages.append(
            ChatMessage(role="assistant", content=f"收到：{state['message']}")
        )
        if state.get("persist_response", True):
            self.store.save(conversation)
        return {"conversation": conversation, "response": object()}


class NegativeFeedbackUnderstandingService:
    """按消息内容返回确定性负反馈理解，避免并发测试依赖 LLM。"""

    def understand(self, *, message, conversation):
        brand = message.removeprefix("不要")
        return UserUnderstanding(
            intent=UserIntent.UPDATE_PREFERENCE,
            confidence=0.9,
            negative_updates={"excluded_brands": [brand]},
        )


def _make_runner(store, *, session_lock_enabled=True):
    from agent.graph.runner import LangGraphAgentRunner

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=lambda query, top_k=3: {}),
        session_lock_manager=SessionLockManager(),
        session_lock_enabled=session_lock_enabled,
    )
    runner.graph = EchoGraph(store)
    return runner


def _empty_recommendation(query: str, top_k: int = 3, negative_filters=None):
    return {
        "query": query,
        "filters": {
            "category": "数码电子",
            "max_price": None,
            "brand": None,
            "keywords": ["手机"],
        },
        "items": [],
    }


def test_langgraph_runner_serializes_same_session_and_preserves_messages():
    store = CopyOnReadConversationStore()
    runner = _make_runner(store)
    messages = [f"并发消息 {index}" for index in range(8)]

    with ThreadPoolExecutor(max_workers=len(messages)) as executor:
        list(executor.map(lambda message: runner.run("same-session", message), messages))

    saved = store.get_or_create("same-session")

    assert len(saved.messages) == len(messages) * 2
    assert {message.content for message in saved.messages if message.role == "user"} == set(
        messages
    )
    assert {
        message.content.replace("收到：", "")
        for message in saved.messages
        if message.role == "assistant"
    } == set(messages)


def test_langgraph_runner_can_disable_session_lock_for_rollback():
    store = NonVersionedCopyOnReadConversationStore()
    runner = _make_runner(store, session_lock_enabled=False)
    messages = [f"未加锁消息 {index}" for index in range(6)]

    with ThreadPoolExecutor(max_workers=len(messages)) as executor:
        list(executor.map(lambda message: runner.run("unlocked-session", message), messages))

    saved = store.get_or_create("unlocked-session")

    assert len(saved.messages) < len(messages) * 2


def test_langgraph_runner_preserves_concurrent_negative_feedback_updates():
    from agent.graph.runner import LangGraphAgentRunner

    store = CopyOnReadConversationStore()
    conversation = store.get_or_create("negative-feedback-session")
    conversation.purchase_need = "推荐手机"
    conversation.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
    }
    conversation.last_successful_items = [
        ProductCard(
            product_id="p_apple",
            title="苹果手机",
            brand="苹果",
            price=5999,
            reason="seed",
            evidence="seed",
        )
    ]
    store.save(conversation)
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=_empty_recommendation),
        understanding_service=NegativeFeedbackUnderstandingService(),
        session_lock_manager=SessionLockManager(),
    )
    messages = ["不要苹果", "不要华为", "不要小米"]

    with ThreadPoolExecutor(max_workers=len(messages)) as executor:
        list(
            executor.map(
                lambda message: runner.run("negative-feedback-session", message),
                messages,
            )
        )

    saved = store.get_or_create("negative-feedback-session")

    assert set(saved.excluded_brands) == {"苹果", "华为", "小米"}


def test_session_lock_manager_allows_different_sessions_to_overlap():
    manager = SessionLockManager()
    events: list[str] = []

    def run_locked(session_id: str):
        with manager.locked(session_id):
            events.append(f"{session_id}:start")
            time.sleep(0.08)
            events.append(f"{session_id}:end")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(run_locked, ["session-a", "session-b"]))
    elapsed = time.perf_counter() - started

    assert elapsed < 0.14
    assert "session-a:start" in events
    assert "session-b:start" in events


def test_langgraph_runner_allows_different_sessions_to_overlap_with_memory_store():
    store = InMemoryConversationStore()
    runner = _make_runner(store)
    runner.graph = EchoGraph(store, delay_seconds=0.08)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(
            executor.map(
                lambda args: runner.run(args[0], args[1]),
                [("memory-session-a", "消息 A"), ("memory-session-b", "消息 B")],
            )
        )
    elapsed = time.perf_counter() - started

    assert elapsed < 0.14
    assert len(store.get_or_create("memory-session-a").messages) == 2
    assert len(store.get_or_create("memory-session-b").messages) == 2


def test_session_lock_manager_records_wait_duration_for_contended_session():
    manager = SessionLockManager()

    def hold_lock():
        with manager.locked("contended"):
            time.sleep(0.05)

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(hold_lock)
        time.sleep(0.01)
        with manager.locked("contended") as lock_info:
            assert lock_info.wait_ms > 0
        first.result()
