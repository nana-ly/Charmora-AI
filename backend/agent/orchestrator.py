"""Agent 编排器。

编排器负责串联：读取状态、判断意图、调用工具、更新状态、生成响应。
它不直接实现检索或推荐细节，从而方便后续替换成图式编排或更复杂的规划器。
"""

from agent.memory import ConversationState, InMemoryConversationStore
from agent.policy import AgentIntent, AgentPolicy
from agent.tools import RecommendationTool
from schemas.chat import ChatMessage, ChatResponse
from schemas.product import ProductCard
from schemas.recommend import RecommendResponse


class SimpleAgentRunner:
    """轻量多轮导购 Agent。"""

    def __init__(
        self,
        store: InMemoryConversationStore,
        recommendation_tool: RecommendationTool,
        policy: AgentPolicy,
    ):
        self.store = store
        self.recommendation_tool = recommendation_tool
        self.policy = policy

    def run(self, session_id: str, message: str) -> ChatResponse:
        """处理一轮用户消息并返回对话响应。"""
        state = self.store.get_or_create(session_id)
        state.messages.append(ChatMessage(role="user", content=message))

        decision = self.policy.detect_intent(message)
        if decision.intent == AgentIntent.RECOMMEND:
            result = self.recommendation_tool.run(message)
            self._save_recommendation_result(state, result)
            reply = "我根据你的需求筛选了这几款商品，可以先看第一款的匹配理由。"
            items = result.items
        elif decision.intent == AgentIntent.UPDATE_PREFERENCE:
            reply, items = self._handle_update_preference(message, state)
        elif decision.intent == AgentIntent.EXPLAIN:
            reply, items = self._handle_explain(state.last_items)
        else:
            reply, items = self._handle_clarify()

        state.last_intent = decision.intent.value
        state.messages.append(ChatMessage(role="assistant", content=reply))
        self.store.save(state)

        return ChatResponse(
            session_id=session_id,
            reply=reply,
            items=items,
            state={
                "intent": decision.intent.value,
                # 返回状态快照，避免后续轮次修改内存状态时污染已返回的响应对象。
                "preferences": state.preferences.copy(),
            },
        )

    def _save_recommendation_result(
        self,
        state: ConversationState,
        result: RecommendResponse,
    ) -> None:
        """保存推荐结果和结构化偏好，供后续追问或调整使用。"""
        state.last_query = result.query
        state.last_filters = result.filters
        state.last_items = result.items
        state.preferences.update(result.filters.model_dump(exclude_none=True))

    def _handle_update_preference(
        self,
        message: str,
        state: ConversationState,
    ) -> tuple[str, list[ProductCard]]:
        """处理基于上一轮的偏好调整。"""
        state.preferences["price_preference"] = "lower"
        # 跟进偏好通常省略品类和预算，需要拼回上一轮原始需求，避免检索跳到无关品类。
        follow_up_query = f"{state.last_query or ''} {message}".strip()
        result = self.recommendation_tool.run(follow_up_query or message)
        self._save_recommendation_result(state, result)
        state.preferences["price_preference"] = "lower"
        reply = "我已按更低预算重新调整推荐，优先保留和上一轮相近的需求。"
        return reply, result.items

    def _handle_explain(self, items: list[ProductCard]) -> tuple[str, list[ProductCard]]:
        """解释上一轮推荐结果。"""
        if not items:
            return "我还没有上一轮推荐结果，可以先告诉我品类、预算和偏好。", []

        first_item = items[0]
        reply = f"因为{first_item.evidence}，所以我优先推荐 {first_item.title}。"
        return reply, items

    def _handle_clarify(self) -> tuple[str, list[ProductCard]]:
        """信息不足时追问关键条件。"""
        return "可以告诉我想买的品类、预算和最在意的点吗？", []
