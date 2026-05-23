"""推荐核心内置关键词检索模块。

阶段 3 会把检索抽象迁移到独立 retrieval 包；当前模块先承接原有行为，
保证阶段 2 只做内部拆分，不改变推荐结果。
"""

from typing import Any

from recommendation_core.data import products
from recommendation_core.filters import extract_filters
from recommendation_core.ranking import get_product_price


def build_searchable_text(product: dict[str, Any]) -> str:
    """拼接商品可检索文本，供关键词检索做命中匹配。"""
    return " ".join(
        [
            str(product.get("title", "")),
            str(product.get("brand", "")),
            str(product.get("category", "")),
            str(product.get("sub_category", "")),
            str(product.get("rag_knowledge", {}).get("marketing_description", "")),
        ]
    )


def retrieve(
    query: str,
    candidates: list[dict[str, Any]] | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """临时检索函数：按关键词命中数排序，返回带 evidence 的 Top K 商品。"""
    source = products if candidates is None else candidates
    query_terms = extract_filters(query)["keywords"]

    def score_product(product: dict[str, Any]) -> int:
        searchable_text = build_searchable_text(product)
        return sum(1 for term in query_terms if term and term in searchable_text)

    ranked_products = sorted(
        source,
        key=lambda product: (score_product(product), -get_product_price(product)),
        reverse=True,
    )

    results = []
    for product in ranked_products[:top_k]:
        searchable_text = build_searchable_text(product)
        matched_terms = [
            term
            for term in query_terms
            if term and term in searchable_text
        ]
        evidence_terms = "、".join(matched_terms) if matched_terms else "结构化筛选"
        results.append(
            {
                "product": product,
                "evidence": f"临时匹配：命中 {evidence_terms}；来自结构化筛选结果。",
            }
        )

    return results

