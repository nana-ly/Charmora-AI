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
    """选择候选商品；无结果时按品牌、预算、品类、全库的顺序逐步兜底。"""
    candidates = structured_filter(products, filters)
    if candidates:
        return candidates

    # 兜底 1：先去掉品牌限制，保留品类和预算，避免品牌偏好过窄导致空结果。
    relaxed_filters = dict(filters)
    relaxed_filters["brand"] = None
    candidates = structured_filter(products, relaxed_filters)
    if candidates:
        return candidates

    # 兜底 2：再去掉预算限制，保留品类，让演示优先展示相关商品。
    relaxed_filters["max_price"] = None
    candidates = structured_filter(products, relaxed_filters)
    if candidates:
        return candidates

    # 兜底 3：如果品类下仍无商品，则退回全库检索，最后由检索层再排序。
    return products

