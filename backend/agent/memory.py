"""对话状态存储模块。"""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from collections.abc import Iterator
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from agent.category_rules import canonical_target_key
from agent.negative_feedback_models import NegativeFeedbackItem
from agent.state_models import PurchasePreferences
from schemas.chat import ChatMessage
from schemas.product import ProductCard
from schemas.recommend import ExcludedPriceRange, RecommendFilters


class PurchaseContext(BaseModel):
    """已归档的购买上下文，用于跨品类切换后恢复。"""

    purchase_need: str
    preferences: dict[str, Any] = Field(default_factory=dict)
    excluded_product_ids: list[str] = Field(default_factory=list)
    excluded_brands: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    excluded_price_ranges: list[ExcludedPriceRange] = Field(default_factory=list)
    negative_feedback_items: list[NegativeFeedbackItem] = Field(default_factory=list)
    latest_attempt_status: Literal["success", "no_results", "tool_error"] | None = None
    latest_attempt_error: str | None = None
    latest_no_results_relax_options: list[str] = Field(default_factory=list)
    last_successful_items: list[ProductCard] = Field(default_factory=list)
    last_successful_result_id: str | None = None
    last_successful_query: str | None = None
    last_successful_filters: RecommendFilters | None = None
    last_query: str | None = None
    last_filters: RecommendFilters | None = None
    last_items: list[ProductCard] = Field(default_factory=list)
    last_result_status: str | None = None
    last_no_results_need: str | None = None
    last_no_results_relax_options: list[str] = Field(default_factory=list)
    target_category: str | None = None
    category: str | None = None
    canonical_target_key: str | None = None
    display_target_category: str | None = None

    @classmethod
    def from_conversation(cls, conversation: "ConversationState") -> "PurchaseContext":
        preferences = deepcopy(conversation.preferences)
        preferences.pop("is_broad_category_request", None)
        target_category = preferences.get("target_category")
        category = preferences.get("category")
        canonical_key = preferences.get("canonical_target_key")
        if not isinstance(canonical_key, str) or not canonical_key.strip():
            canonical_key = canonical_target_key(
                target_category if isinstance(target_category, str) else None,
                category if isinstance(category, str) else None,
            )
        display_target = target_category if isinstance(target_category, str) else None

        return cls(
            purchase_need=conversation.purchase_need or "",
            preferences=preferences,
            excluded_product_ids=deepcopy(conversation.excluded_product_ids),
            excluded_brands=deepcopy(conversation.excluded_brands),
            excluded_keywords=deepcopy(conversation.excluded_keywords),
            excluded_price_ranges=deepcopy(conversation.excluded_price_ranges),
            negative_feedback_items=deepcopy(conversation.negative_feedback_items),
            latest_attempt_status=conversation.latest_attempt_status,
            latest_attempt_error=conversation.latest_attempt_error,
            latest_no_results_relax_options=deepcopy(
                conversation.latest_no_results_relax_options
            ),
            last_successful_items=deepcopy(conversation.last_successful_items),
            last_successful_result_id=conversation.last_successful_result_id,
            last_successful_query=conversation.last_successful_query,
            last_successful_filters=deepcopy(conversation.last_successful_filters),
            last_query=conversation.last_query,
            last_filters=deepcopy(conversation.last_filters),
            last_items=deepcopy(conversation.last_items),
            last_result_status=conversation.last_result_status,
            last_no_results_need=conversation.last_no_results_need,
            last_no_results_relax_options=deepcopy(conversation.last_no_results_relax_options),
            target_category=target_category if isinstance(target_category, str) else None,
            category=category if isinstance(category, str) else None,
            canonical_target_key=canonical_key if isinstance(canonical_key, str) else None,
            display_target_category=display_target,
        )

    def apply_to_conversation(self, conversation: "ConversationState") -> None:
        conversation.purchase_need = self.purchase_need
        conversation.excluded_product_ids = deepcopy(self.excluded_product_ids)
        conversation.excluded_brands = deepcopy(self.excluded_brands)
        conversation.excluded_keywords = deepcopy(self.excluded_keywords)
        conversation.excluded_price_ranges = deepcopy(self.excluded_price_ranges)
        conversation.negative_feedback_items = deepcopy(self.negative_feedback_items)
        conversation.latest_attempt_status = self.latest_attempt_status
        conversation.latest_attempt_error = self.latest_attempt_error
        conversation.latest_no_results_relax_options = deepcopy(
            self.latest_no_results_relax_options
        )
        conversation.last_successful_items = deepcopy(self.last_successful_items)
        conversation.last_successful_result_id = self.last_successful_result_id
        conversation.last_successful_query = self.last_successful_query
        conversation.last_successful_filters = deepcopy(self.last_successful_filters)
        conversation.target_item_index = None
        conversation.last_query = self.last_query
        conversation.last_filters = deepcopy(self.last_filters)
        conversation.last_items = deepcopy(self.last_items)
        conversation.last_result_status = self.last_result_status
        conversation.last_no_results_need = self.last_no_results_need
        conversation.last_no_results_relax_options = deepcopy(self.last_no_results_relax_options)
        conversation.preferences = deepcopy(self.preferences)
        if self.canonical_target_key:
            conversation.preferences["canonical_target_key"] = self.canonical_target_key
        if self.target_category:
            conversation.preferences["target_category"] = self.target_category
        if self.category:
            conversation.preferences["category"] = self.category
        conversation.preferences["is_broad_category_request"] = False


class ConversationState(BaseModel):
    """单个会话的对话状态。

    当前先使用内存存储，字段设计保留持久化空间：历史消息、偏好、最近推荐结果和最近意图。
    """

    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    purchase_need: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    excluded_product_ids: list[str] = Field(default_factory=list)
    excluded_brands: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    excluded_price_ranges: list[ExcludedPriceRange] = Field(default_factory=list)
    negative_feedback_items: list[NegativeFeedbackItem] = Field(default_factory=list)
    latest_attempt_status: Literal["success", "no_results", "tool_error"] | None = None
    latest_attempt_error: str | None = None
    latest_no_results_relax_options: list[str] = Field(default_factory=list)
    last_successful_items: list[ProductCard] = Field(default_factory=list)
    last_successful_result_id: str | None = None
    last_successful_query: str | None = None
    last_successful_filters: RecommendFilters | None = None
    target_item_index: int | None = None
    last_query: str | None = None
    last_filters: RecommendFilters | None = None
    last_items: list[ProductCard] = Field(default_factory=list)
    last_result_status: str | None = None
    last_no_results_need: str | None = None
    last_no_results_relax_options: list[str] = Field(default_factory=list)
    last_intent: str | None = None
    previous_purchase_contexts: list[PurchaseContext] = Field(default_factory=list)
    pending_restore_category: str | None = None
    pending_restore_display_target: str | None = None

    def preferences_model(self) -> PurchasePreferences:
        """以 typed helper 读取偏好，持久化层仍保留 dict 兼容旧会话。"""
        return PurchasePreferences.from_dict(self.preferences)

    def apply_preferences_model(self, model: PurchasePreferences) -> None:
        """把 typed helper 写回 dict，确保旧 JSON 字段不会被意外丢掉。"""
        self.preferences = model.to_dict()


@runtime_checkable
class ConversationStore(Protocol):
    """会话状态存储接口。

    Runner 只依赖这个最小接口；具体实现可以是内存、Redis 或 SQLite。
    """

    def get_or_create(self, session_id: str) -> ConversationState:
        """获取会话状态；不存在时创建空状态。"""
        ...

    def save(self, state: ConversationState) -> None:
        """保存会话状态。"""
        ...


@dataclass(frozen=True)
class SessionLockInfo:
    """一次会话锁获取结果，用于观测等待耗时。"""

    session_id: str
    wait_ms: float


class SessionLockManager:
    """按 session_id 维护进程内锁。

    这层锁只保护当前 Python 进程内的并发 Runner 调用；多 worker、多实例仍需要
    Redis/Postgres 等外部一致性机制，不能把它视为分布式锁。
    """

    def __init__(self):
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    @contextmanager
    def locked(self, session_id: str) -> Iterator[SessionLockInfo]:
        """获取指定会话的可重入锁，并返回本次等待耗时。"""
        lock = self._get_lock(session_id)
        started_at = time.perf_counter()
        lock.acquire()
        wait_ms = (time.perf_counter() - started_at) * 1000
        try:
            yield SessionLockInfo(session_id=session_id, wait_ms=wait_ms)
        finally:
            lock.release()

    def _get_lock(self, session_id: str) -> threading.RLock:
        # 锁表创建本身需要单独保护，避免同一个 session 并发创建出两把锁。
        with self._locks_guard:
            if session_id not in self._locks:
                self._locks[session_id] = threading.RLock()
            return self._locks[session_id]


class InMemoryConversationStore:
    """内存会话存储。

    适合本地最小闭环；生产环境可按同样接口替换为 Redis、数据库或向量记忆模块。
    """

    def __init__(self):
        self._states: dict[str, ConversationState] = {}

    def get_or_create(self, session_id: str) -> ConversationState:
        """获取会话状态；不存在时创建空状态。"""
        if session_id not in self._states:
            self._states[session_id] = ConversationState(session_id=session_id)
        return self._states[session_id]

    def save(self, state: ConversationState) -> None:
        """保存会话状态。"""
        self._states[state.session_id] = state
