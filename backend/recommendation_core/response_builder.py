"""推荐响应组装模块。"""

from typing import Any

from recommendation_core.image_url import product_image_fields
from recommendation_core.ranking import get_product_price
from recommendation_core.reason import ReasonService, generate_reason


def build_response_item(
    query: str,
    retrieved_item: dict[str, Any],
    reason_service: ReasonService | None = None,
) -> dict[str, Any]:
    """把检索结果转换成 Android 商品卡片需要的稳定字段。"""
    product = retrieved_item.get("product", retrieved_item)
    evidence = retrieved_item.get("evidence", "匹配用户需求和商品信息。")

    skus = product.get("skus", [])
    rag = product.get("rag_knowledge", {})
    reviews = rag.get("user_reviews", [])
    faqs = rag.get("official_faq", [])

    return {
        "product_id": product.get("product_id", ""),
        "title": product.get("title", ""),
        "brand": product.get("brand", ""),
        "price": get_product_price(product),
        "price_range": _build_price_range(skus, get_product_price(product)),
        "reason": generate_reason(query, product, evidence, reason_service=reason_service),
        "evidence": evidence,
        **product_image_fields(product),
        "rating": _avg_rating(reviews),
        "sold_count": len(reviews) * 500,
        "review_count": len(reviews),
        "marketing_desc": rag.get("marketing_description", ""),
        "reviews": [{"nickname": r.get("nickname", ""), "rating": r.get("rating", 5), "content": r.get("content", "")} for r in reviews],
        "faqs": [{"question": f.get("question", ""), "answer": f.get("answer", "")} for f in faqs],
    }


def _avg_rating(reviews: list[dict]) -> float:
    if not reviews:
        return 0.0
    ratings = [int(r["rating"]) for r in reviews if "rating" in r]
    if not ratings:
        return 0.0
    return round(sum(ratings) / len(ratings), 1)


def _build_price_range(skus: list[dict], base_price: float) -> str:
    if not skus:
        return f"¥{base_price:.0f}"
    prices = [float(s.get("price", base_price)) for s in skus]
    lo, hi = min(prices), max(prices)
    if lo == hi:
        return f"¥{lo:.0f}"
    return f"¥{lo:.0f}-{hi:.0f}"
