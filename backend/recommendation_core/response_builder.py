"""推荐响应组装模块。"""

from typing import Any

from recommendation_core.ranking import get_product_price
from recommendation_core.reason import generate_reason


def build_response_item(query: str, retrieved_item: dict[str, Any]) -> dict[str, Any]:
    """把检索结果转换成 Android 商品卡片需要的稳定字段。"""
    product = retrieved_item.get("product", retrieved_item)
    evidence = retrieved_item.get("evidence", "匹配用户需求和商品信息。")

    return {
        "product_id": product.get("product_id", ""),
        "title": product.get("title", ""),
        "brand": product.get("brand", ""),
        "price": get_product_price(product),
        "reason": generate_reason(query, product, evidence),
        "evidence": evidence,
    }

