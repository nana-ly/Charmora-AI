"""LangGraph 版导购 Agent Runner。

首版只把现有 SimpleAgentRunner 的多轮流程迁移到图编排：
识别意图 -> 按意图路由到工具节点 -> 统一保存状态并组装 ChatResponse。
"""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.memory import ConversationState, InMemoryConversationStore
from agent.policy import AgentDecision, AgentIntent, AgentPolicy
from agent.tools import RecommendationTool
from schemas.chat import ChatMessage, ChatResponse
from schemas.product import ProductCard
from schemas.recommend import RecommendResponse


class ShoppingAgentState(TypedDict, total=False):
    """LangGraph 节点之间共享的状态。

    这里保留 ConversationState 对象，是为了首版复用现有内存会话存储；
    后续接入 checkpoint 时，可以再把字段拆成更细的可序列化状态。
    """

    session_id: str
    message: str
    conversation: ConversationState
    decision: AgentDecision
    reply: str
    items: list[ProductCard]
    response: ChatResponse


RouteName = Literal["recommend", "update_preference", "explain", "clarify"]


class LangGraphAgentRunner:
    """基于 LangGraph 的多轮导购 Agent。"""

    def __init__(
        self,
        store: InMemoryConversationStore,
        recommendation_tool: RecommendationTool,
        policy: AgentPolicy,
    ):
        self.store = store
        self.recommendation_tool = recommendation_tool
        self.policy = policy
        self.graph = self._build_graph()

    def run(self, session_id: str, message: str) -> ChatResponse:
        """处理一轮用户消息，并保持与 SimpleAgentRunner 相同的响应契约。"""
        result = self.graph.invoke({"session_id": session_id, "message": message})
        return result["response"]

    def _build_graph(self):
        """构建首版导购状态图。"""
        graph = StateGraph(ShoppingAgentState)
        graph.add_node("detect_intent", self._detect_intent)
        graph.add_node("recommend", self._recommend)
        graph.add_node("update_preference", self._update_preference)
        graph.add_node("explain", self._explain)
        graph.add_node("clarify", self._clarify)
        graph.add_node("finalize", self._finalize)

        graph.add_edge(START, "detect_intent")
        # 条件边只负责选择业务节点，避免 API 层理解具体意图分支。
        graph.add_conditional_edges(
            "detect_intent",
            self._route_by_intent,
            {
                AgentIntent.RECOMMEND.value: "recommend",
                AgentIntent.UPDATE_PREFERENCE.value: "update_preference",
                AgentIntent.EXPLAIN.value: "explain",
                AgentIntent.CLARIFY.value: "clarify",
            },
        )
        graph.add_edge("recommend", "finalize")
        graph.add_edge("update_preference", "finalize")
        graph.add_edge("explain", "finalize")
        graph.add_edge("clarify", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _detect_intent(self, state: ShoppingAgentState) -> dict[str, Any]:
        """读取/创建会话状态，并判断本轮用户意图。"""
        conversation = self.store.get_or_create(state["session_id"])
        conversation.messages.append(ChatMessage(role="user", content=state["message"]))
        decision = self.policy.detect_intent(state["message"])
        return {"conversation": conversation, "decision": decision}

    def _route_by_intent(self, state: ShoppingAgentState) -> RouteName:
        """把意图结果映射到 LangGraph 节点名称。"""
        return state["decision"].intent.value  # type: ignore[return-value]

    def _recommend(self, state: ShoppingAgentState) -> dict[str, Any]:
        """执行推荐工具节点。"""
        result = self.recommendation_tool.run(state["message"])
        self._save_recommendation_result(state["conversation"], result)
        return {
            "reply": "我根据你的需求筛选了这几款商品，可以先看第一款的匹配理由。",
            "items": result.items,
        }

    def _update_preference(self, state: ShoppingAgentState) -> dict[str, Any]:
        """基于上一轮需求处理偏好调整节点。"""
        conversation = state["conversation"]
        conversation.preferences["price_preference"] = "lower"
        # 跟进偏好通常省略品类和预算，需要拼回上一轮原始需求，避免检索跳到无关品类。
        follow_up_query = f"{conversation.last_query or ''} {state['message']}".strip()
        result = self.recommendation_tool.run(follow_up_query or state["message"])
        self._save_recommendation_result(conversation, result)
        conversation.preferences["price_preference"] = "lower"
        return {
            "reply": "我已按更低预算重新调整推荐，优先保留和上一轮相近的需求。",
            "items": result.items,
        }

    def _explain(self, state: ShoppingAgentState) -> dict[str, Any]:
        """解释上一轮推荐结果节点。"""
        items = state["conversation"].last_items
        if not items:
            return {
                "reply": "我还没有上一轮推荐结果，可以先告诉我品类、预算和偏好。",
                "items": [],
            }

        first_item = items[0]
        return {
            "reply": f"因为{first_item.evidence}，所以我优先推荐 {first_item.title}。",
            "items": items,
        }

    def _clarify(self, state: ShoppingAgentState) -> dict[str, Any]:
        """信息不足时追问关键条件节点。"""
        return {"reply": "可以告诉我想买的品类、预算和最在意的点吗？", "items": []}

    def _finalize(self, state: ShoppingAgentState) -> dict[str, ChatResponse]:
        """保存会话并组装对外响应。

        响应中的 preferences 使用 copy，避免后续轮次修改内存状态时污染已返回对象。
        """
        conversation = state["conversation"]
        decision = state["decision"]
        reply = state["reply"]
        items = state["items"]

        conversation.last_intent = decision.intent.value
        conversation.messages.append(ChatMessage(role="assistant", content=reply))
        self.store.save(conversation)

        return {
            "response": ChatResponse(
                session_id=state["session_id"],
                reply=reply,
                items=items,
                state={
                    "intent": decision.intent.value,
                    "preferences": conversation.preferences.copy(),
                },
            )
        }

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
