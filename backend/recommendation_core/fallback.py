"""推荐兜底结果模块。"""

from typing import Any


def fallback_items(query: str) -> list[dict[str, Any]]:
    """返回固定 3 张兜底商品卡片，避免前端页面因为空结果无法展示。"""
    return [
        {
            "product_id": "fallback_001",
            "title": "通用推荐商品 1",
            "brand": "系统推荐",
            "price": 0,
            "reason": f"当前根据「{query}」返回兜底推荐，真实检索结果暂不可用。",
            "evidence": "后端兜底逻辑触发。",
        },
        {
            "product_id": "fallback_002",
            "title": "通用推荐商品 2",
            "brand": "系统推荐",
            "price": 0,
            "reason": f"当前根据「{query}」返回兜底推荐，用于保证演示链路不中断。",
            "evidence": "真实推荐链路无结果时返回。",
        },
        {
            "product_id": "fallback_003",
            "title": "通用推荐商品 3",
            "brand": "系统推荐",
            "price": 0,
            "reason": f"当前根据「{query}」返回兜底推荐，后续可替换为真实商品。",
            "evidence": "检索或数据模块不可用时返回。",
        },
    ]

