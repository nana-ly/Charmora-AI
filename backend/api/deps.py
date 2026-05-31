"""API 共享依赖和应用级单例。"""

from agent.runner import create_agent_runner
from agent.tools import RecommendationTool
from schemas.chat import ChatResponse
from services.recommendation_service import get_recommendation_service


recommendation_service = get_recommendation_service()


def run_recommendation(query, top_k=None, negative_filters=None, include_trace=False):
    """共享推荐服务入口，供 API 和 Agent 工具复用同一份缓存。"""
    return recommendation_service.recommend(
        query,
        top_k=top_k,
        negative_filters=negative_filters,
        include_trace=include_trace,
    )


agent_runner = create_agent_runner(
    recommendation_tool=RecommendationTool(recommend_func=run_recommendation),
)


def run_chat(session_id: str, message: str) -> ChatResponse:
    """执行一轮 Agent 对话。"""
    return agent_runner.run(session_id, message)
