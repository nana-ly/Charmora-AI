"""导购 Agent 模块。"""

from typing import Any

from agent.memory import ConversationStore, InMemoryConversationStore
from agent.understanding import UserIntent, UserUnderstanding

__all__ = [
    "InMemoryConversationStore",
    "ConversationStore",
    "RecommendationTool",
    "UserIntent",
    "UserUnderstanding",
]


def __getattr__(name: str) -> Any:
    """按需导入工具门面，避免基础模型导入时触发推荐链路循环依赖。"""
    if name == "RecommendationTool":
        from agent.tools import RecommendationTool

        return RecommendationTool
    raise AttributeError(f"module 'agent' has no attribute {name!r}")

