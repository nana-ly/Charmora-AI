"""推荐链路编排模块。

该模块只负责编排：解析需求、筛选候选、调用检索、组装响应和异常兜底。
具体策略放在独立模块中，便于后续把检索替换成向量库，或把理由生成替换成 LLM。
"""

from collections.abc import Callable
from typing import Any

from recommendation_core.data import products
from recommendation_core.fallback import fallback_items
from recommendation_core.filters import EMPTY_FILTERS, extract_filters
from recommendation_core.ranking import choose_candidates
from recommendation_core.response_builder import build_response_item
from recommendation_core.reason import ReasonService
from retrieval.keyword import retrieve


def recommend_products(
    query: str,
    product_source: list[dict[str, Any]] | None = None,
    top_k: int = 3,
    retrieve_func: Callable[..., list[dict[str, Any]]] = retrieve,
    reason_service: ReasonService | None = None,
) -> dict[str, Any]:
    """组装完整推荐链路，并在检索为空或异常时返回稳定兜底结果。"""
    try:
        filters = extract_filters(query)
        # None 表示使用默认商品库，空列表表示外部数据源暂时无商品，需要走兜底。
        selected_products = products if product_source is None else product_source
        candidates = choose_candidates(selected_products, filters)
        retrieved_items = retrieve_func(query, candidates=candidates, top_k=top_k)
        items = [
            build_response_item(query, item, reason_service=reason_service)
            for item in retrieved_items
        ]

        if not items:
            items = fallback_items(query)

        return {
            "query": query,
            "filters": filters,
            "items": items,
        }
    except Exception as exc:
        return {
            "query": query,
            "filters": {
                "category": EMPTY_FILTERS["category"],
                "max_price": EMPTY_FILTERS["max_price"],
                "brand": EMPTY_FILTERS["brand"],
                "keywords": list(EMPTY_FILTERS["keywords"]),
            },
            "items": fallback_items(query),
            "error": str(exc),
        }
