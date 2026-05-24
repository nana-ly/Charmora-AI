"""轻量 Agent 模块。

当前实现不依赖 LangChain/LangGraph，而是先固定好可扩展边界：
状态存储、意图策略、工具调用和编排器。后续如果流程复杂，再替换编排器即可。
"""

from agent.memory import InMemoryConversationStore
from agent.orchestrator import SimpleAgentRunner
from agent.policy import AgentIntent, AgentPolicy
from agent.tools import RecommendationTool

__all__ = [
    "AgentIntent",
    "AgentPolicy",
    "InMemoryConversationStore",
    "RecommendationTool",
    "SimpleAgentRunner",
]

