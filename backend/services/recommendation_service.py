"""API 路由和 Agent 工具共用的推荐应用服务。"""

from typing import Any

from core.config import load_app_config
from recommendation_core.pipeline import recommend_products
from schemas.recommend import NegativeFilters
from services.retriever_factory import select_retriever


def run_recommendation(
    query: str,
    top_k: int | None = None,
    negative_filters: NegativeFilters | None = None,
) -> dict[str, Any]:
    """按当前配置执行推荐链路。"""
    config = load_app_config()
    selected_top_k = top_k if top_k is not None else config.default_top_k
    retriever = select_retriever(config)
    kwargs: dict[str, Any] = {
        "top_k": selected_top_k,
        "retriever": retriever,
    }
    if negative_filters is not None:
        kwargs["negative_filters"] = negative_filters
    return recommend_products(query, **kwargs)
