"""推荐核心模块聚合入口。

这里统一导出推荐链路的稳定函数，旧的 recommendation.py 会继续从这里转发，
从而保证现有接口和测试不需要立刻跟随内部拆分调整。
"""

from recommendation_core.data import DATASET_DIR, load_products, products
from recommendation_core.fallback import fallback_items
from recommendation_core.filters import CATEGORY_RULES, EMPTY_FILTERS, extract_filters
from recommendation_core.pipeline import recommend_products
from recommendation_core.ranking import (
    choose_candidates,
    get_product_price,
    structured_filter,
)
from recommendation_core.response_builder import build_response_item
from recommendation_core.retrieval import build_searchable_text, retrieve

__all__ = [
    "CATEGORY_RULES",
    "DATASET_DIR",
    "EMPTY_FILTERS",
    "build_response_item",
    "build_searchable_text",
    "choose_candidates",
    "extract_filters",
    "fallback_items",
    "get_product_price",
    "load_products",
    "products",
    "recommend_products",
    "retrieve",
    "structured_filter",
]

