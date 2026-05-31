"""Agent 工具门面，保持旧导入路径兼容。"""

from agent.tools.compare import CompareTool
from agent.tools.explain import ExplainTool
from agent.tools.recommendation import RecommendationTool

__all__ = [
    "RecommendationTool",
    "ExplainTool",
    "CompareTool",
]
