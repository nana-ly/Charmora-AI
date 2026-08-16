from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProductSkuView(BaseModel):
    id: UUID
    external_id: str
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    active: bool
    available_quantity: int
    price: Decimal | None
    currency: str = "CNY"


class ProductView(BaseModel):
    id: UUID
    external_id: str
    category_id: UUID
    category_name: str
    source_key: str
    title: str
    brand: str
    description: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    active: bool
    images: list[str] = Field(default_factory=list)
    skus: list[ProductSkuView] = Field(default_factory=list)


class ProductListResponse(BaseModel):
    items: list[ProductView]
    offset: int
    limit: int
    total: int = 0


class CategoryView(BaseModel):
    id: UUID
    external_key: str
    name: str
    product_count: int = 0


class CategoryListResponse(BaseModel):
    items: list[CategoryView]


class InventoryView(BaseModel):
    product_id: UUID
    skus: list[ProductSkuView]


class VectorSyncJobView(BaseModel):
    id: UUID
    product_id: UUID
    operation: str
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
