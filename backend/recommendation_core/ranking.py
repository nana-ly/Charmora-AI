"""候选商品筛选与排序辅助模块。"""

from typing import Any


_CATEGORY_ALIASES = {
    "食品生活": {"食品生活", "食品饮料"},
}


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

        if filters.get("category") and not _same_category(
            product_category,
            filters["category"],
        ):
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


def _same_category(product_category: Any, requested_category: Any) -> bool:
    """兼容 taxonomy 与历史商品数据中的食品类目命名差异。"""
    if product_category == requested_category:
        return True
    aliases = _CATEGORY_ALIASES.get(str(requested_category), set())
    return str(product_category) in aliases

