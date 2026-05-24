import logging
from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from agent.memory import InMemoryConversationStore
from agent.orchestrator import SimpleAgentRunner
from agent.policy import AgentPolicy
from agent.tools import RecommendationTool
from recommendation import recommend_products
from schemas.chat import ChatRequest, ChatResponse
from schemas.recommend import RecommendRequest
from sse import sse_event


app = FastAPI(title="ShopGuide RAG API")
logger = logging.getLogger(__name__)

agent_runner = SimpleAgentRunner(
    store=InMemoryConversationStore(),
    recommendation_tool=RecommendationTool(),
    policy=AgentPolicy(),
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
    return recommend_products(request.query)


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
