"""对话接口数据结构。"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from schemas.product import ProductCard


class ChatRequest(BaseModel):
    """多轮对话请求体。"""

    session_id: str
    message: str


class ChatMessage(BaseModel):
    """单条对话消息，用于后续持久化或上下文压缩。"""

    role: str
    content: str


class ChatResponse(BaseModel):
    """多轮对话响应体。"""

    session_id: str
    reply: str
    result_count: int | None = None
    items: list[ProductCard] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def default_result_count(self):
        if self.result_count is None:
            self.result_count = len(self.items)
        return self

