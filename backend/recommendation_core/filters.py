"""用户需求解析模块。

该模块把自然语言需求先转成可观察、可测试的结构化筛选条件。
后续如果接入 LLM 意图识别，也应先输出同样的数据结构，再交给推荐链路使用。
"""

import re
from typing import Any

from agent.catalog_taxonomy import (
    brand_terms,
    category_keywords,
    detect_catalog_category,
)

CATEGORY_KEYWORDS = category_keywords()
CATEGORY_RULES = CATEGORY_KEYWORDS
BRAND_RULES = list(brand_terms())
EMPTY_FILTERS: dict[str, Any] = {
    "category": None,
    "max_price": None,
    "brand": None,
    "keywords": [],
}


def _detect_category(query: str) -> str | None:
    return detect_catalog_category(query)


def create_empty_filters() -> dict[str, Any]:
    """创建新的空筛选条件，避免多个请求共享 keywords 列表。"""
    return {
        "category": EMPTY_FILTERS["category"],
        "max_price": EMPTY_FILTERS["max_price"],
        "brand": EMPTY_FILTERS["brand"],
        "keywords": list(EMPTY_FILTERS["keywords"]),
    }


def extract_filters(query: str) -> dict[str, Any]:
    """从用户自然语言需求中解析基础筛选条件。"""
    filters = create_empty_filters()

    category = _detect_category(query)
    if category:
        filters["category"] = category
        filters["keywords"].extend(
            word for word in CATEGORY_KEYWORDS[category] if word in query
        )

    price_match = re.search(
        r"(?:预算\s*)?(\d+)\s*(?:以内|以下|左右|不超过)?|不超过\s*(\d+)",
        query,
    )
    if price_match:
        filters["max_price"] = int(price_match.group(1) or price_match.group(2))

    for brand in BRAND_RULES:
        if brand in query:
            filters["brand"] = brand
            break

    return filters

