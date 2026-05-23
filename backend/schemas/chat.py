"""对话接口数据结构。"""

from typing import Any

from pydantic import BaseModel, Field

from schemas.product import ProductCard


class ChatRequest(BaseModel):
    """多轮对话请求体。"""

    session_id: str
    message: str


class ChatMessage(BaseModel):
    """单条对话消息，用于后续持久化或上下文压缩。"""

    role: str
    content: str


class ConversationStateSnapshot(BaseModel):
    """对话状态快照，便于接口层返回可观察的状态摘要。"""

    intent: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """多轮对话响应体。"""

    session_id: str
    reply: str
    items: list[ProductCard] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

