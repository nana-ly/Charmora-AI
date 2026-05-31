"""推荐接口数据结构。"""

from pydantic import BaseModel, Field

from schemas.product import ProductCard


class RecommendRequest(BaseModel):
    """推荐接口请求体，接收用户的自然语言需求。"""

    query: str
    debug: bool = False


class ExcludedPriceRange(BaseModel):
    """预留的价格区间排除结构。"""

    min_price: float | None = None
    max_price: float | None = None
    reason: str | None = None
    source_product_id: str | None = None


class NegativeFilters(BaseModel):
    """推荐链使用的负向过滤条件。"""

    excluded_product_ids: list[str] = Field(default_factory=list)
    excluded_brands: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    excluded_price_ranges: list[ExcludedPriceRange] = Field(default_factory=list)


class RecommendFilters(BaseModel):
    """从用户需求中解析出的结构化筛选条件。"""

    category: str | None = None
    max_price: int | None = None
    brand: str | None = None
    keywords: list[str] = Field(default_factory=list)


class RecommendationTraceItem(BaseModel):
    """单个推荐结果的脱敏检索 trace。"""

    product_id: str
    title: str | None = None
    brand: str | None = None
    rank: int | None = None
    score: float | None = None
    score_type: str | None = None
    source: str | None = None
    evidence: str | None = None
    retriever_mode: str | None = None


class RecommendationTrace(BaseModel):
    """推荐链路内部调试 trace，默认不向普通响应暴露。"""

    retriever_mode: str | None = None
    query_length: int
    top_k: int
    source_count: int
    structured_candidate_count: int
    negative_filtered_candidate_count: int
    retrieved_count: int
    final_count: int
    negative_filter_applied: bool
    items: list[RecommendationTraceItem] = Field(default_factory=list)
    dropped: list[dict[str, str]] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    """推荐接口响应体。"""

    query: str
    filters: RecommendFilters
    items: list[ProductCard] = Field(default_factory=list)
    trace: RecommendationTrace | None = None

