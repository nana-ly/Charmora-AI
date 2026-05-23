"""推荐链路兼容入口。

真实实现已经拆到 recommendation_core 包中。本文件保留原有导入路径，
避免 FastAPI 路由、测试和外部调用方因为内部架构调整而需要同步改动。
"""

from recommendation_core import (
    CATEGORY_RULES,
    DATASET_DIR,
    EMPTY_FILTERS,
    build_response_item,
    build_searchable_text,
    choose_candidates,
    extract_filters,
    fallback_items,
    get_product_price,
    load_products,
    products,
    recommend_products,
    retrieve,
    structured_filter,
)

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
