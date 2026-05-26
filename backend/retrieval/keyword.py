"""关键词检索实现。

这是本地最小闭环的默认检索器：使用解析出的关键词命中数排序，
返回商品和 evidence。后续接入向量库时，可以继续保留它作为降级策略。
"""

from typing import Any

from retrieval.base import RetrievalResult, Retriever


FIELD_WEIGHTS = {
    "title": 3,
    "sub_category": 3,
    "brand": 2,
    "category": 1,
    "description": 1,
}

TERM_SYNONYMS = {
    "拍照": ["拍照", "摄影", "影像", "人像", "相机", "超感光"],
    "剪视频": ["剪视频", "视频", "Vlog", "vlog", "创作", "剪辑"],
}


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


def _score_product(product: dict[str, Any], query_terms: list[str]) -> int:
    """计算关键词相关性分数，避免低价但品类不符的商品排在前面。"""
    title = str(product.get("title", ""))
    brand = str(product.get("brand", ""))
    category = str(product.get("category", ""))
    sub_category = str(product.get("sub_category", ""))
    description = str(product.get("rag_knowledge", {}).get("marketing_description", ""))

    score = 0
    for term in query_terms:
        if not term:
            continue
        match_terms = TERM_SYNONYMS.get(term, [term])
        if any(match_term in title for match_term in match_terms):
            score += FIELD_WEIGHTS["title"]
        if any(match_term in sub_category for match_term in match_terms):
            score += FIELD_WEIGHTS["sub_category"]
        if any(match_term in brand for match_term in match_terms):
            score += FIELD_WEIGHTS["brand"]
        if any(match_term in category for match_term in match_terms):
            score += FIELD_WEIGHTS["category"]
        if any(match_term in description for match_term in match_terms):
            score += FIELD_WEIGHTS["description"]

    if "手机" in query_terms and sub_category == "智能手机":
        score += 3

    return score


def _matched_query_terms(product: dict[str, Any], query_terms: list[str]) -> list[str]:
    """返回命中的原始查询词；同义词命中时也展示用户说过的词。"""
    searchable_text = build_searchable_text(product)
    matched_terms: list[str] = []
    for term in query_terms:
        if not term:
            continue
        match_terms = TERM_SYNONYMS.get(term, [term])
        if any(match_term in searchable_text for match_term in match_terms):
            matched_terms.append(term)
    return matched_terms


class KeywordRetriever(Retriever):
    """基于关键词命中的本地检索器。"""

    def search(
        self,
        query: str,
        candidates: list[dict[str, Any]] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        """按关键词命中数排序，返回带 evidence 的 Top K 商品。"""
        # 延迟导入推荐核心模块，避免检索层导入期与 recommendation_core.__init__ 形成循环依赖。
        from recommendation_core.data import products
        from recommendation_core.filters import extract_filters
        from recommendation_core.ranking import get_product_price

        source = products if candidates is None else candidates
        query_terms = extract_filters(query)["keywords"]

        ranked_products = sorted(
            source,
            key=lambda product: (_score_product(product, query_terms), -get_product_price(product)),
            reverse=True,
        )

        results: list[RetrievalResult] = []
        for product in ranked_products[:top_k]:
            matched_terms = _matched_query_terms(product, query_terms)
            evidence_terms = "、".join(matched_terms) if matched_terms else "结构化筛选"
            results.append(
                RetrievalResult(
                    product=product,
                    evidence=f"临时匹配：命中 {evidence_terms}；来自结构化筛选结果。",
                    score=float(_score_product(product, query_terms)),
                )
            )

        return results


def retrieve(
    query: str,
    candidates: list[dict[str, Any]] | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """兼容旧链路的检索函数，返回原有字典结构。"""
    return [
        result.to_legacy_item()
        for result in KeywordRetriever().search(query, candidates=candidates, top_k=top_k)
    ]
