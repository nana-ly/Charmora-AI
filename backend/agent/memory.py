"""对话状态存储模块。"""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from schemas.chat import ChatMessage
from schemas.product import ProductCard
from schemas.recommend import RecommendFilters


class PurchaseContext(BaseModel):
    """已归档的购买上下文，用于跨品类切换后恢复。"""

    purchase_need: str
    preferences: dict[str, Any] = Field(default_factory=dict)
    excluded_brands: list[str] = Field(default_factory=list)
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
            excluded_brands=deepcopy(conversation.excluded_brands),
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
        conversation.excluded_brands = deepcopy(self.excluded_brands)
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
    excluded_brands: list[str] = Field(default_factory=list)
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
