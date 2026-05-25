"""Agent Runner 工厂。

API 层只依赖 AgentRunner 协议，不关心内部使用规则编排还是 LangGraph 编排。
这样后续切换实现时，可以保持 /chat 和 /chat/stream 的外部契约稳定。
"""

from typing import Protocol

from agent.memory import InMemoryConversationStore
from agent.orchestrator import SimpleAgentRunner
from agent.policy import AgentPolicy
from agent.tools import RecommendationTool
from core.config import AppConfig, load_app_config
from schemas.chat import ChatResponse


class AgentRunner(Protocol):
    """多轮导购 Agent 的统一入口协议。"""

    def run(self, session_id: str, message: str) -> ChatResponse:
        """处理一轮用户消息并返回稳定的 ChatResponse。"""
        ...


def create_agent_runner(
    *,
    config: AppConfig | None = None,
    store: InMemoryConversationStore | None = None,
    recommendation_tool: RecommendationTool | None = None,
    policy: AgentPolicy | None = None,
) -> AgentRunner:
    """根据 AGENT_RUNNER 创建 AgentRunner。

    默认使用 simple，保证本地最小闭环不依赖 LangGraph；设置为 langgraph 时只替换编排层，
    推荐、检索、RAG fallback 仍通过 RecommendationTool 间接复用现有后端入口。
    """
    selected_config = config or load_app_config()
    runner_name = selected_config.agent_runner.strip().lower()
    shared_store = store or InMemoryConversationStore()
    shared_tool = recommendation_tool or RecommendationTool()
    shared_policy = policy or AgentPolicy()

    if runner_name == "simple":
        return SimpleAgentRunner(
            store=shared_store,
            recommendation_tool=shared_tool,
            policy=shared_policy,
        )

    if runner_name == "langgraph":
        from agent.graph.runner import LangGraphAgentRunner

        return LangGraphAgentRunner(
            store=shared_store,
            recommendation_tool=shared_tool,
            policy=shared_policy,
        )

    raise ValueError("AGENT_RUNNER 仅支持 simple 或 langgraph")
