"""向量检索适配器占位。

向量数据库由独立模块接入时，只需要实现 search 方法并返回 RetrievalResult 列表。
当前显式抛出未实现异常，避免误以为已经有真实向量召回能力。
"""

from typing import Any

from retrieval.base import RetrievalResult, Retriever


class VectorRetriever(Retriever):
    """向量检索器接口占位。"""

    def search(
        self,
        query: str,
        candidates: list[dict[str, Any]] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        """等待向量数据库模块接入后实现真实召回。"""
        raise NotImplementedError("向量检索模块尚未接入，请先使用 KeywordRetriever。")

