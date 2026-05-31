import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

import api.deps as api_deps

router = APIRouter()
logger = logging.getLogger(__name__)


class RagSearchRequest(BaseModel):
    """RAG 调试检索请求。"""

    query: str
    top_k: int = Field(default=5, ge=1, le=20)


@router.post("/rag/search")
def rag_search(request: RagSearchRequest) -> dict[str, Any]:
    """返回原始向量检索调试结果。"""
    logger.info("rag search request received")
    logger.debug("rag search query_length=%s top_k=%s", len(request.query), request.top_k)
    results = api_deps.recommendation_service.search(request.query, top_k=request.top_k)
    logger.info("rag search response generated item_count=%s", len(results))
    return {
        "query": request.query,
        "items": [
            {
                "product_id": result.product.get("product_id", ""),
                "title": result.product.get("title", ""),
                "brand": result.product.get("brand", ""),
                "score": result.score,
                "rank": result.rank,
                "source": result.source,
                "retriever_mode": result.retriever_mode,
                "score_type": result.score_type,
                "evidence": result.evidence,
                "metadata": result.metadata or {},
            }
            for result in results
        ],
    }
