"""推荐接口数据结构。"""

from pydantic import BaseModel, Field

from schemas.product import ProductCard


class RecommendRequest(BaseModel):
    """推荐接口请求体，接收用户的自然语言需求。"""

    query: str


class RecommendFilters(BaseModel):
    """从用户需求中解析出的结构化筛选条件。"""

    category: str | None = None
    max_price: int | None = None
    brand: str | None = None
    keywords: list[str] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    """推荐接口响应体。"""

    query: str
    filters: RecommendFilters
    items: list[ProductCard] = Field(default_factory=list)

