"""用户需求解析模块。

该模块把自然语言需求先转成可观察、可测试的结构化筛选条件。
后续如果接入 LLM 意图识别，也应先输出同样的数据结构，再交给推荐链路使用。
"""

import re
from collections.abc import Sequence
from typing import Any


CATEGORY_KEYWORDS: dict[str, Sequence[str]] = {
    "数码电子": (
        "手机",
        "耳机",
        "电脑",
        "拍照",
        "剪视频",
        "平板",
        "笔记本",
        "续航",
        "游戏",
        "办公",
        "学生",
        "降噪",
    ),
    "美妆护肤": (
        "护肤产品",
        "护肤品",
        "化妆品",
        "美妆",
        "精华",
        "敏感肌",
        "护肤",
        "抗初老",
        "面霜",
        "防晒",
        "保湿",
        "修护",
        "美白",
        "油皮",
        "干皮",
    ),
    "服饰运动": (
        "T恤",
        "通勤",
        "运动",
        "凉快",
        "速干",
        "外套",
        "夏天",
        "跑步",
        "健身",
        "防晒衣",
    ),
    "食品生活": (
        "咖啡",
        "速溶",
        "饮品",
        "新手",
        "拿铁",
        "冷萃",
        "低糖",
        "早餐",
        "办公室",
        "精品",
    ),
}
CATEGORY_RULES = CATEGORY_KEYWORDS
BRAND_RULES = ["Apple", "苹果", "小米", "华为", "雅诗兰黛", "优衣库", "三顿半"]
EMPTY_FILTERS: dict[str, Any] = {
    "category": None,
    "max_price": None,
    "brand": None,
    "keywords": [],
}


def _detect_category(query: str) -> str | None:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return category
    return None


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

