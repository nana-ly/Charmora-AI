"""Agent 侧负反馈状态模型。"""

from typing import Literal

from pydantic import BaseModel, Field


class NegativeFeedbackItem(BaseModel):
    """记录的负反馈项，用于状态和归档复用。"""

    product_id: str | None = None
    title: str = ""
    brand: str = ""
    price: float | None = None
    reason: str | None = None
    source: str = "chat"
    active: bool = True
    source_result_id: str | None = None
    source_target_key: str | None = None
    source_item_index: int | None = None
    feedback_type: str | None = None


class NegativeFeedbackApplicationResult(BaseModel):
    """应用一次负反馈更新后的结果。"""

    detected: bool = False
    applied: bool = False
    removed: bool = False
    noop: bool = False
    needs_clarification: bool = False
    clarifying_question: str | None = None
    ack_message: str | None = None
    invalid_reason: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    target_product_ids: list[str] = Field(default_factory=list)
    target_brands: list[str] = Field(default_factory=list)
    noop_reason: Literal[
        "already_excluded",
        "not_currently_excluded",
        "unknown_brand",
        "unsupported_negative_type",
    ] | None = None
