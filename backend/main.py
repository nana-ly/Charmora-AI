from fastapi import FastAPI

from agent.memory import InMemoryConversationStore
from agent.orchestrator import SimpleAgentRunner
from agent.policy import AgentPolicy
from agent.tools import RecommendationTool
from recommendation import recommend_products
from schemas.chat import ChatRequest, ChatResponse
from schemas.recommend import RecommendRequest


app = FastAPI(title="ShopGuide RAG API")

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
