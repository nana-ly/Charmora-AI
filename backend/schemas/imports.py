from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ProductSkuImport(BaseModel):
    external_id: str
    name: str = "默认规格"
    attributes: dict[str, Any] = Field(default_factory=dict)
    price: Decimal = Field(ge=0)
    inventory: int = Field(default=0, ge=0)
    active: bool = True


class ProductImportRecord(BaseModel):
    external_id: str
    title: str
    brand: str = ""
    category: str
    sub_category: str | None = None
    description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list)
    skus: list[ProductSkuImport] = Field(default_factory=list)
    active: bool = True

    @model_validator(mode="after")
    def require_sku(self):
        if not self.skus:
            raise ValueError("at least one sku is required")
        return self


class ImportBatchView(BaseModel):
    id: UUID
    source_key: str
    filename: str | None
    status: str
    total_count: int
    success_count: int
    failure_count: int
    errors: list[dict[str, Any]]
    created_at: datetime
    completed_at: datetime | None


class ImportBatchListResponse(BaseModel):
    items: list[ImportBatchView]
    offset: int
    limit: int
