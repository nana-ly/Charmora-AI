"""候选商品筛选与排序辅助模块。"""

from typing import Any


def get_product_price(product: dict[str, Any]) -> float:
    """统一读取商品价格，兼容数据中的 base_price 和 price 字段。"""
    if "base_price" in product:
        return float(product["base_price"])
    if "price" in product:
        return float(product["price"])
    return 0.0


def structured_filter(
    products: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """根据品类、预算和品牌对商品列表做第一轮结构化筛选。"""
    results = []

    for product in products:
        product_category = product.get("category")
        product_brand = product.get("brand", "")
        product_price = get_product_price(product)

        if filters.get("category") and product_category != filters["category"]:
            continue

        if filters.get("max_price") and product_price > filters["max_price"]:
            continue

        if filters.get("brand") and filters["brand"] not in product_brand:
            continue

        results.append(product)

    return results


def choose_candidates(
    products: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """选择候选商品；无结果时返回空列表，不放宽用户给出的约束。"""
    return structured_filter(products, filters)

