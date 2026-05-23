"""对话状态存储模块。"""

from typing import Any

from pydantic import BaseModel, Field

from schemas.chat import ChatMessage
from schemas.product import ProductCard
from schemas.recommend import RecommendFilters


class ConversationState(BaseModel):
    """单个会话的对话状态。

    当前先使用内存存储，字段设计保留持久化空间：历史消息、偏好、最近推荐结果和最近意图。
    """

    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    last_query: str | None = None
    last_filters: RecommendFilters | None = None
    last_items: list[ProductCard] = Field(default_factory=list)
    last_intent: str | None = None


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
