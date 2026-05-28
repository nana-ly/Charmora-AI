"""API 共享依赖和应用级单例。"""

from agent.runner import create_agent_runner
from agent.tools import RecommendationTool
from schemas.chat import ChatResponse
from services.recommendation_service import run_recommendation


agent_runner = create_agent_runner(
    recommendation_tool=RecommendationTool(recommend_func=run_recommendation),
)


def run_chat(session_id: str, message: str) -> ChatResponse:
    """执行一轮 Agent 对话。"""
    return agent_runner.run(session_id, message)
