import logging
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.runner import create_agent_runner
from agent.tools import RecommendationTool
from core.config import load_app_config
from recommendation import recommend_products
from retrieval.keyword import retrieve as keyword_retrieve
from retrieval.vector import VectorRetriever
from schemas.chat import ChatRequest, ChatResponse
from schemas.recommend import RecommendRequest
from sse import sse_event


app = FastAPI(title="ShopGuide RAG API")
logger = logging.getLogger(__name__)

class RagSearchRequest(BaseModel):
    """RAG 调试检索请求。"""

    query: str
    top_k: int = Field(default=5, ge=1, le=20)


def create_vector_retriever() -> VectorRetriever:
    """创建真实向量检索器；测试中可 monkeypatch 以避免外部 embedding 调用。"""
    config = load_app_config()
    return VectorRetriever(
        embedding_base_url=config.rag.embedding_url or None,
        embedding_api_key=config.rag.embedding_api or None,
        embedding_model=config.rag.embedding_model,
        embedding_dimensions=config.rag.embedding_dimensions,
    )


def _legacy_retrieve_from_retriever(retriever: Any):
    def retrieve_func(query: str, candidates=None, top_k: int = 3):
        try:
            return [
                result.to_legacy_item()
                for result in retriever.search(query, candidates=candidates, top_k=top_k)
            ]
        except Exception:
            logger.exception("vector search failed; falling back to keyword")
            return keyword_retrieve(query, candidates=candidates, top_k=top_k)

    return retrieve_func


def _select_retrieve_func():
    config = load_app_config()
    if config.retriever_mode.lower() == "vector":
        try:
            return _legacy_retrieve_from_retriever(create_vector_retriever())
        except Exception:
            logger.exception("vector retriever unavailable; falling back to keyword")
            return None
    return None


def run_recommendation(query: str, top_k: int = 3) -> dict:
    """统一推荐入口，供 /recommend 和 Agent 工具共用。"""
    retrieve_func = _select_retrieve_func()
    if retrieve_func is None:
        return recommend_products(query, top_k=top_k)
    return recommend_products(query, top_k=top_k, retrieve_func=retrieve_func)


agent_runner = create_agent_runner(
    recommendation_tool=RecommendationTool(recommend_func=run_recommendation),
)


@app.get("/")
def read_root() -> dict[str, str]:
    """返回服务基础信息，用于确认后端应用已经启动。"""
    return {
        "name": "ShopGuide RAG API",
        "status": "running",
    }


@app.get("/health")
def read_health() -> dict[str, str]:
    """健康检查接口，用于验证 FastAPI 服务是否可访问。"""
    return {"status": "ok"}


@app.post("/recommend")
def recommend(request: RecommendRequest) -> dict:
    """推荐接口：调用完整推荐链路，并保证异常时也返回稳定商品卡片。"""
    return run_recommendation(request.query)


@app.post("/rag/search")
def rag_search(request: RagSearchRequest) -> dict[str, Any]:
    """RAG 调试接口：直接返回向量检索结果，便于验证索引和召回质量。"""
    results = create_vector_retriever().search(request.query, top_k=request.top_k)
    return {
        "query": request.query,
        "items": [
            {
                "product_id": result.product.get("product_id", ""),
                "title": result.product.get("title", ""),
                "brand": result.product.get("brand", ""),
                "score": result.score,
                "evidence": result.evidence,
            }
            for result in results
        ],
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """多轮对话接口：通过轻量 Agent 维护会话状态并调用推荐工具。"""
    return agent_runner.run(request.session_id, request.message)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """多轮对话 SSE 接口：按事件推送回复、商品和状态。"""

    def event_generator() -> Iterator[str]:
        yield sse_event("start", {"session_id": request.session_id})

        try:
            response = agent_runner.run(request.session_id, request.message)
            success_events = [
                sse_event("delta", {"text": response.reply}),
                sse_event(
                    "items",
                    {"items": [item.model_dump() for item in response.items]},
                ),
                sse_event("state", {"state": response.state}),
            ]
            yield from success_events
        except Exception:
            logger.exception("chat stream failed")
            yield sse_event(
                "error",
                {"message": "服务暂时不可用，请稍后再试。"},
            )
        finally:
            yield sse_event("done")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
