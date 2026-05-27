"""检索器创建和检索模式选择。"""

import logging
from collections.abc import Callable
from typing import Any

from core.config import AppConfig, load_app_config
from retrieval.base import Retriever
from retrieval.keyword import KeywordRetriever
from retrieval.vector import VectorRetriever

logger = logging.getLogger(__name__)


def create_vector_retriever(config: AppConfig | None = None) -> VectorRetriever:
    """根据应用配置创建向量检索器。"""
    selected_config = config or load_app_config()
    return VectorRetriever(
        embedding_base_url=selected_config.rag.embedding_url or None,
        embedding_api_key=selected_config.rag.embedding_api or None,
        embedding_model=selected_config.rag.embedding_model,
        embedding_dimensions=selected_config.rag.embedding_dimensions,
    )


def legacy_retrieve_from_retriever(retriever: Any) -> Callable[..., list[dict[str, Any]]]:
    """把检索器适配为旧推荐链路使用的函数形态。"""

    def retrieve_func(query: str, candidates=None, top_k: int = 3):
        return [
            result.to_legacy_item()
            for result in retriever.search(query, candidates=candidates, top_k=top_k)
        ]

    return retrieve_func


def select_retriever(config: AppConfig | None = None) -> Retriever:
    """按配置返回检索器对象，供新推荐链路直接调用 search。"""
    selected_config = config or load_app_config()
    retriever_mode = selected_config.retriever_mode.lower()
    logger.debug("select retriever mode=%s", retriever_mode)
    if retriever_mode == "keyword":
        logger.info("using keyword retriever")
        return KeywordRetriever()
    if retriever_mode == "vector":
        logger.info("using vector retriever")
        return create_vector_retriever(selected_config)
    raise ValueError("RETRIEVER_MODE 仅支持 vector 或 keyword")


def select_retrieve_func(
    config: AppConfig | None = None,
) -> Callable[..., list[dict[str, Any]]] | None:
    """向量模式返回向量检索函数，关键词模式返回 None。"""
    selected_config = config or load_app_config()
    retriever_mode = selected_config.retriever_mode.lower()
    logger.debug("select retriever mode=%s", retriever_mode)
    if retriever_mode == "keyword":
        logger.info("using keyword retriever")
        return None
    if retriever_mode != "vector":
        raise ValueError("RETRIEVER_MODE 仅支持 vector 或 keyword")

    logger.info("using vector retriever")
    return legacy_retrieve_from_retriever(create_vector_retriever(selected_config))
