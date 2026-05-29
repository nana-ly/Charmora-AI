"""推荐核心模块聚合入口。

这里统一导出推荐链路的稳定函数，旧的 recommendation.py 会继续从这里转发，
从而保证现有接口和测试不需要立刻跟随内部拆分调整。
"""

from recommendation_core.data import DATASET_DIR, load_products, products
from recommendation_core.filters import CATEGORY_RULES, EMPTY_FILTERS, extract_filters
from recommendation_core.negative_filter import (
    apply_negative_filters,
    has_negative_filters,
    normalize_brand_key,
    passes_negative_filter,
)
from recommendation_core.pipeline import recommend_products
from recommendation_core.ranking import (
    choose_candidates,
    get_product_price,
    structured_filter,
)
from recommendation_core.response_builder import build_response_item
from retrieval.keyword import build_searchable_text

__all__ = [
    "CATEGORY_RULES",
    "DATASET_DIR",
    "EMPTY_FILTERS",
    "apply_negative_filters",
    "build_response_item",
    "build_searchable_text",
    "choose_candidates",
    "extract_filters",
    "get_product_price",
    "has_negative_filters",
    "load_products",
    "normalize_brand_key",
    "passes_negative_filter",
    "products",
    "recommend_products",
    "structured_filter",
]
