"""推荐链路编排模块。

该模块只负责编排：解析需求、筛选候选、调用检索和组装响应。
空结果会如实返回空列表；基础设施或代码异常会向上抛出，避免伪造商品结果。
"""

from typing import Any

from recommendation_core.data import products
from recommendation_core.filters import extract_filters
from recommendation_core.negative_filter import apply_negative_filters, passes_negative_filter
from recommendation_core.ranking import choose_candidates
from recommendation_core.response_builder import build_response_item
from recommendation_core.reason import ReasonService
from retrieval.base import Retriever
from retrieval.keyword import KeywordRetriever
from schemas.recommend import NegativeFilters


def create_default_reason_service() -> ReasonService:
    """创建默认推荐理由服务。

    服务会读取 .env/环境变量中的 LLM 配置；如果未开启 LLM 或缺少 API Key，
    LLMReasonService 会自动回退到模板理由，保证推荐主链路稳定。
    """
    from core.config import load_app_config
    from llm.reason_service import LLMReasonService

    return LLMReasonService(config=load_app_config().llm)


def recommend_products(
    query: str,
    product_source: list[dict[str, Any]] | None = None,
    top_k: int = 3,
    retriever: Retriever | None = None,
    reason_service: ReasonService | None = None,
    negative_filters: NegativeFilters | None = None,
) -> dict[str, Any]:
    """组装完整推荐链路；不为无结果或异常伪造推荐商品。"""
    active_reason_service = reason_service or create_default_reason_service()
    filters = extract_filters(query)
    # None 表示使用默认商品库；空列表表示调用方明确传入了空数据源。
    selected_products = products if product_source is None else product_source
    candidates = apply_negative_filters(
        choose_candidates(selected_products, filters),
        negative_filters,
    )
    active_retriever = retriever or KeywordRetriever()
    retrieval_results = active_retriever.search(query, candidates=candidates, top_k=top_k)
    items = []
    for result in retrieval_results:
        # 最终安全过滤，防止 retriever 忽略候选约束。
        if not passes_negative_filter(result.product, negative_filters):
            continue
        items.append(
            build_response_item(
                query,
                {
                    "product": result.product,
                    "evidence": result.evidence,
                    "score": result.score,
                },
                reason_service=active_reason_service,
            )
        )

    return {
        "query": query,
        "filters": filters,
        "items": items,
    }
