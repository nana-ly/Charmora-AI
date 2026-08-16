from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AddCartItemRequest(BaseModel):
    sku_id: UUID
    quantity: int = Field(ge=1, le=99)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1, le=99)


class CartItemView(BaseModel):
    sku_id: UUID
    product_id: UUID
    title: str
    sku_name: str
    quantity: int
    available_quantity: int
    unit_price: Decimal
    currency: str
    image_url: str | None = None


class CartView(BaseModel):
    session_id: str
    items: list[CartItemView] = Field(default_factory=list)
    total_amount: Decimal = Decimal("0")
    currency: str = "CNY"


class CreateOrderRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)
    confirmation_token: str | None = Field(default=None, min_length=1, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)
    recipient_name: str = Field(default="演示用户", min_length=1, max_length=100)
    recipient_phone: str = Field(default="13800000000", min_length=6, max_length=30)
    shipping_address: str = Field(default="演示地址", min_length=1, max_length=500)
    customer_note: str = Field(default="", max_length=500)
    payment_method: str = "demo_wechat"

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, value: str) -> str:
        allowed = {"demo_wechat", "demo_alipay", "demo_bank_card"}
        if value not in allowed:
            raise ValueError("unsupported simulated payment method")
        return value


class CheckoutPreviewRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=200)


class CheckoutPreviewView(BaseModel):
    confirmation_token: str
    session_id: str
    items: list[CartItemView]
    total_amount: Decimal
    currency: str = "CNY"
    expires_at: datetime


class OrderItemView(BaseModel):
    sku_id: UUID
    product_id: UUID
    product_title: str
    sku_name: str
    quantity: int
    unit_price: Decimal
    image_url: str | None = None


class OrderView(BaseModel):
    id: UUID
    session_id: str
    status: str
    total_amount: Decimal
    currency: str
    recipient_name: str = ""
    recipient_phone: str = ""
    shipping_address: str = ""
    customer_note: str = ""
    payment_method: str = "demo_wechat"
    payment_status: str = "simulated_paid"
    created_at: datetime
    cancelled_at: datetime | None = None
    items: list[OrderItemView]
    status_events: list["OrderStatusEventView"] = Field(default_factory=list)


class OrderStatusEventView(BaseModel):
    from_status: str | None
    to_status: str
    reason: str
    created_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderView]
    offset: int
    limit: int
    total: int
