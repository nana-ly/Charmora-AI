"""API 路由和 Agent 工具共用的推荐应用服务。"""

from typing import Any

from core.config import load_app_config
from recommendation_core.pipeline import recommend_products
from services.retriever_factory import select_retrieve_func


def run_recommendation(query: str, top_k: int | None = None) -> dict[str, Any]:
    """按当前配置执行推荐链路。"""
    config = load_app_config()
    selected_top_k = top_k if top_k is not None else config.default_top_k
    retrieve_func = select_retrieve_func(config)
    if retrieve_func is None:
        return recommend_products(query, top_k=selected_top_k)
    return recommend_products(query, top_k=selected_top_k, retrieve_func=retrieve_func)
