from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.catalog import ProductView


class ImageUnderstandingResponse(BaseModel):
    asset_id: str
    description: str


class ImageSearchResponse(BaseModel):
    asset_id: str
    items: list[ProductView]


class AsrResponse(BaseModel):
    text: str


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
