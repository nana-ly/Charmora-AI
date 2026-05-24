"""关键词检索实现。

这是本地最小闭环的默认检索器：使用解析出的关键词命中数排序，
返回商品和 evidence。后续接入向量库时，可以继续保留它作为降级策略。
"""

from typing import Any

from retrieval.base import RetrievalResult, Retriever


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

        def score_product(product: dict[str, Any]) -> int:
            searchable_text = build_searchable_text(product)
            return sum(1 for term in query_terms if term and term in searchable_text)

        ranked_products = sorted(
            source,
            key=lambda product: (score_product(product), -get_product_price(product)),
            reverse=True,
        )

        results: list[RetrievalResult] = []
        for product in ranked_products[:top_k]:
            searchable_text = build_searchable_text(product)
            matched_terms = [
                term
                for term in query_terms
                if term and term in searchable_text
            ]
            evidence_terms = "、".join(matched_terms) if matched_terms else "结构化筛选"
            results.append(
                RetrievalResult(
                    product=product,
                    evidence=f"临时匹配：命中 {evidence_terms}；来自结构化筛选结果。",
                    score=float(score_product(product)),
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
