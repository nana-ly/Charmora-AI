"""检索器创建和检索模式选择。"""

import logging

from core.config import AppConfig, load_app_config
from retrieval.base import Retriever
from retrieval.keyword import KeywordRetriever
from retrieval.vector import VectorRetriever
from retrieval.database_vector import DatabaseBackedVectorRetriever
from db.session import create_database_runtime

logger = logging.getLogger(__name__)


def create_vector_retriever(config: AppConfig | None = None) -> Retriever:
    """根据应用配置创建向量检索器。"""
    selected_config = config or load_app_config()
    vector = VectorRetriever(
        embedding_base_url=selected_config.rag.embedding_url or None,
        embedding_api_key=selected_config.rag.embedding_api or None,
        embedding_model=selected_config.rag.embedding_model,
        embedding_dimensions=selected_config.rag.embedding_dimensions,
    )
    if selected_config.catalog_source.lower() == "postgresql":
        return DatabaseBackedVectorRetriever(
            vector.store,
            create_database_runtime(selected_config.database),
        )
    return vector


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
