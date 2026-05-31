"""Agent Runner 工厂。

API 层只依赖 AgentRunner 协议，不关心 LangGraph Runner 的内部编排细节。
这样后续调整实现时，可以保持 /chat 和 /chat/stream 的外部契约稳定。
"""

from typing import Protocol

from agent.memory import ConversationStore, InMemoryConversationStore, SessionLockManager
from agent.tools import RecommendationTool
from agent.understanding import LLMUserUnderstandingService, UserUnderstandingService
from core.config import AppConfig, load_app_config
from schemas.chat import ChatResponse


class AgentRunner(Protocol):
    """多轮导购 Agent 的统一入口协议。"""

    def run(self, session_id: str, message: str) -> ChatResponse:
        """处理一轮用户消息并返回稳定的 ChatResponse。"""
        ...


def create_conversation_store(config: AppConfig) -> ConversationStore:
    """按配置创建会话存储；显式注入 store 时不会调用这里。"""
    mode = config.conversation_store_mode.strip().lower()
    if mode == "memory":
        return InMemoryConversationStore()
    if mode == "sqlite":
        from agent.sqlite_memory import SQLiteConversationStore

        return SQLiteConversationStore(config.conversation_store_path)
    raise ValueError("CONVERSATION_STORE_MODE 仅支持 memory 或 sqlite")


def create_agent_runner(
    *,
    config: AppConfig | None = None,
    store: ConversationStore | None = None,
    recommendation_tool: RecommendationTool | None = None,
    understanding_service: UserUnderstandingService | None = None,
) -> AgentRunner:
    """根据 AGENT_RUNNER 创建 AgentRunner。

    当前仅支持 LangGraph 编排。
    推荐、检索、RAG fallback 仍通过 RecommendationTool 间接复用现有后端入口。
    """
    selected_config = config or load_app_config()
    runner_name = selected_config.agent_runner.strip().lower()
    shared_store = store or create_conversation_store(selected_config)
    shared_tool = recommendation_tool or RecommendationTool()
    shared_understanding_service = understanding_service or LLMUserUnderstandingService(
        config=selected_config.llm
    )

    if runner_name == "langgraph":
        from agent.graph.runner import LangGraphAgentRunner

        return LangGraphAgentRunner(
            store=shared_store,
            recommendation_tool=shared_tool,
            understanding_service=shared_understanding_service,
            llm_config=selected_config.llm,
            session_lock_manager=SessionLockManager(),
            session_lock_enabled=selected_config.agent_session_lock_enabled,
        )

    raise ValueError("AGENT_RUNNER 仅支持 langgraph")
