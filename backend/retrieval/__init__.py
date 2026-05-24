"""检索层统一入口。

检索层只负责从候选商品中召回和排序，不负责生成最终推荐理由。
这样后续接入向量数据库时，可以替换 Retriever 实现，而不改推荐编排逻辑。
"""

from retrieval.base import RetrievalResult, Retriever
from retrieval.keyword import KeywordRetriever, build_searchable_text, retrieve
from retrieval.vector import VectorRetriever

__all__ = [
    "KeywordRetriever",
    "RetrievalResult",
    "Retriever",
    "VectorRetriever",
    "build_searchable_text",
    "retrieve",
]

