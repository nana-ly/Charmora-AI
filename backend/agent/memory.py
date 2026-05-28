"""对话状态存储模块。"""

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.negative_feedback_models import NegativeFeedbackItem
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

    @classmethod
    def from_conversation(cls, conversation: "ConversationState") -> "PurchaseContext":
        preferences = deepcopy(conversation.preferences)
        target_category = preferences.get("target_category")
        category = preferences.get("category")

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
        )

    def apply_to_conversation(self, conversation: "ConversationState") -> None:
        conversation.purchase_need = self.purchase_need
        conversation.preferences = deepcopy(self.preferences)
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
