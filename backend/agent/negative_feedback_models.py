"""Agent-side negative feedback state models."""

from typing import Literal

from pydantic import BaseModel, Field


class NegativeFeedbackItem(BaseModel):
    """Recorded negative feedback item for state and archive reuse."""

    product_id: str | None = None
    title: str = ""
    brand: str = ""
    price: float | None = None
    reason: str | None = None
    source: str = "chat"
    active: bool = True


class NegativeFeedbackApplicationResult(BaseModel):
    """Result of applying one negative feedback update."""

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
