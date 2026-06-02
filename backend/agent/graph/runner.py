"""LangGraph 版导购 Agent Runner。"""

import logging
import time
from collections.abc import Callable
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from agent.category_rules import detect_restore_target
from agent.context_manager import (
    ConversationCommand,
    active_target_key,
    clear_pending_restore,
    request_restore,
    resolve_pending_restore,
)
from agent.graph.action_executor import ActionExecutor
from agent.graph.response_state_builder import ResponseStateBuilder
from agent.graph.state_reducer import ConversationStateReducer
from agent.memory import (
    ConversationState,
    ConversationStore,
    SessionLockManager,
    VersionedConversationStore,
)
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.negative_feedback_rules import extract_negative_updates
from agent.policy import decide_next_action
from agent.reply_builder import (
    build_clarify_reply,
    build_compare_reply,
    build_explain_reply,
    build_negative_feedback_noop_reply,
    build_no_results_reply,
    build_recommendation_reply,
    build_tool_error_reply,
)
from agent.tools import RecommendationTool
from agent.understanding import (
    ActionResult,
    AgentAction,
    LLMUserUnderstandingService,
    UserIntent,
    UserUnderstanding,
    UserUnderstandingService,
    clarify_understanding,
)
from core.config import LLMConfig, load_app_config
from core.request_context import get_request_context, set_request_context
from schemas.chat import ChatMessage, ChatResponse
from schemas.product import ProductCard

logger = logging.getLogger(__name__)

class ShoppingAgentState(TypedDict, total=False):
    session_id: str
    message: str
    conversation: ConversationState
    understanding: UserUnderstanding
    negative_feedback_result: NegativeFeedbackApplicationResult
    pending_restore_command: ConversationCommand
    current_turn_is_broad: bool
    action: AgentAction
    action_result: ActionResult
    reply: str
    items: list[ProductCard]
    response: ChatResponse
    persist_response: bool


class LangGraphAgentRunner:
    """基于 LangGraph 的多轮导购 Agent。"""

    def __init__(
        self,
        store: ConversationStore,
        recommendation_tool: RecommendationTool,
        understanding_service: UserUnderstandingService | None = None,
        llm_config: LLMConfig | None = None,
        session_lock_manager: SessionLockManager | None = None,
        session_lock_enabled: bool = True,
    ):
        self.store = store
        self.recommendation_tool = recommendation_tool
        self.llm_config = llm_config or load_app_config().llm
        self.understanding_service = understanding_service or LLMUserUnderstandingService(
            config=self.llm_config
        )
        self.session_lock_manager = session_lock_manager or SessionLockManager()
        self.session_lock_enabled = session_lock_enabled
        self.state_reducer = ConversationStateReducer()
        self.action_executor = ActionExecutor(recommendation_tool)
        self.response_state_builder = ResponseStateBuilder()

        self.graph = self._build_graph()

    def run(self, session_id: str, message: str) -> ChatResponse:
        context = get_request_context()
        request_id = context.request_id if context.request_id != "-" else uuid4().hex
        turn_id = uuid4().hex
        with set_request_context(
            request_id=request_id,
            session_id=session_id,
            turn_id=turn_id,
        ):
            logger.info(
                "agent run started session_id=%s message_length=%s turn_id=%s",
                session_id,
                len(message),
                turn_id,
            )
            if self.session_lock_enabled:
                with self.session_lock_manager.locked(session_id) as lock_info:
                    logger.info(
                        "agent session lock acquired session_id=%s lock_wait_ms=%.3f",
                        session_id,
                        lock_info.wait_ms,
                    )
                    response = self._run_state_update(session_id, message)
            else:
                response = self._run_state_update(session_id, message)
            logger.info("agent run completed session_id=%s turn_id=%s", session_id, turn_id)
        return response

    def _run_state_update(self, session_id: str, message: str) -> ChatResponse:
        """把一整轮图执行包进 store.update()，成功响应后才提交会话状态。"""
        if isinstance(self.store, VersionedConversationStore):
            response_holder: dict[str, ChatResponse] = {}

            def mutate(conversation: ConversationState) -> ConversationState:
                # 冲突重试时 mutate 可能被再次执行；只把最终一次返回的状态交给 store 提交。
                result = self.graph.invoke(
                    {
                        "session_id": session_id,
                        "message": message,
                        "conversation": conversation,
                        "persist_response": False,
                    }
                )
                response_holder["response"] = result["response"]
                return result["conversation"]

            self.store.update(session_id, mutate)
            return response_holder["response"]

        logger.warning(
            "conversation store does not support atomic update; falling back to save path"
        )
        result = self.graph.invoke(
            {
                "session_id": session_id,
                "message": message,
                "persist_response": True,
            }
        )
        return result["response"]

    def _build_graph(self):
        graph = StateGraph(ShoppingAgentState)
        graph.add_node(
            "understand_user",
            self._timed_node("understand_user", self._understand_user),
        )
        graph.add_node(
            "update_memory",
            self._timed_node("update_memory", self._update_memory),
        )
        graph.add_node(
            "decide_next_action",
            self._timed_node("decide_next_action", self._decide_next_action),
        )
        graph.add_node(
            "execute_action",
            self._timed_node("execute_action", self._execute_action),
        )
        graph.add_node(
            "generate_reply",
            self._timed_node("generate_reply", self._generate_reply),
        )
        graph.add_node(
            "finalize_response",
            self._timed_node("finalize_response", self._finalize_response),
        )

        graph.add_edge(START, "understand_user")
        graph.add_edge("understand_user", "update_memory")
        graph.add_edge("update_memory", "decide_next_action")
        graph.add_edge("decide_next_action", "execute_action")
        graph.add_edge("execute_action", "generate_reply")
        graph.add_edge("generate_reply", "finalize_response")
        graph.add_edge("finalize_response", END)
        return graph.compile()

    def _timed_node(
        self,
        node: str,
        handler: Callable[[ShoppingAgentState], dict[str, Any]],
    ) -> Callable[[ShoppingAgentState], dict[str, Any]]:
        """包装 LangGraph 节点，记录耗时和脱敏后的结构化状态。"""

        def wrapped(state: ShoppingAgentState) -> dict[str, Any]:
            started_at = time.perf_counter()
            logger.info("agent node started node=%s", node)
            try:
                output = handler(state)
            except Exception as exc:
                duration_ms = (time.perf_counter() - started_at) * 1000
                logger.exception(
                    "agent node failed node=%s duration_ms=%.3f error_type=%s",
                    node,
                    duration_ms,
                    type(exc).__name__,
                )
                raise

            duration_ms = (time.perf_counter() - started_at) * 1000
            merged_state: ShoppingAgentState = {**state, **output}
            fields = self._node_log_fields(node, merged_state, output)
            logger.info(
                (
                    "agent node completed node=%s duration_ms=%.3f status=ok "
                    "intent=%s action=%s reply_type=%s fallback_reason=%s result_count=%s"
                ),
                node,
                duration_ms,
                fields["intent"],
                fields["action"],
                fields["reply_type"],
                fields["fallback_reason"],
                fields["result_count"],
            )
            return output

        return wrapped

    def _node_log_fields(
        self,
        node: str,
        state: ShoppingAgentState,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        understanding = state.get("understanding")
        action = state.get("action")
        action_result = state.get("action_result")
        items = state.get("items")

        fallback_reason = "-"
        result_count: int | str = "-"
        reply_type = getattr(action_result, "reply_type", "-") if action_result else "-"
        if action_result:
            result_count = len(action_result.items)
            fallback_reason = self._fallback_reason(action_result)
        elif isinstance(items, list):
            result_count = len(items)

        return {
            "node": node,
            "intent": getattr(getattr(understanding, "intent", None), "value", "-"),
            "action": getattr(getattr(action, "value", action), "value", action) or "-",
            "reply_type": reply_type,
            "fallback_reason": fallback_reason,
            "result_count": result_count,
            "output_keys": ",".join(sorted(output)),
        }

    def _fallback_reason(self, action_result: ActionResult) -> str:
        if action_result.tool_error:
            return action_result.tool_error
        if action_result.no_results:
            return "no_results"
        negative_feedback = action_result.negative_feedback
        if negative_feedback and negative_feedback.noop:
            return negative_feedback.noop_reason or "negative_feedback_noop"
        return "-"

    def _understand_user(self, state: ShoppingAgentState) -> dict[str, Any]:
        conversation = state.get("conversation") or self.store.get_or_create(
            state["session_id"]
        )
        message = state["message"]
        conversation.messages.append(ChatMessage(role="user", content=message))

        message_negative_updates = extract_negative_updates(message)
        if conversation.pending_restore_category and message_negative_updates:
            clear_pending_restore(conversation)

        resolution = resolve_pending_restore(conversation, message)
        if resolution.handled:
            understanding = resolution.understanding or clarify_understanding(
                "正在恢复之前的需求。"
            )
            logger.info(
                "agent pending restore resolved command=%s",
                resolution.command.value,
            )
            return {
                "conversation": conversation,
                "understanding": understanding,
                "pending_restore_command": resolution.command,
            }

        if resolution.clear_pending_before_understanding:
            clear_pending_restore(conversation)

        restore_target = detect_restore_target(message)
        if restore_target is not None:
            active_key = active_target_key(conversation)
            if active_key != restore_target.canonical_target_key and request_restore(
                conversation,
                restore_target.canonical_target_key,
                restore_target.target_category,
            ):
                understanding = UserUnderstanding(
                    intent=UserIntent.CLARIFY,
                    confidence=0.8,
                    clarifying_question=(
                        "要恢复之前的"
                        f"{conversation.pending_restore_display_target or restore_target.target_category}"
                        "需求吗？"
                    ),
                    restore_context_category=restore_target.target_category,
                )
                return {"conversation": conversation, "understanding": understanding}

        understanding = self.understanding_service.understand(
            message=message,
            conversation=conversation,
        )

        restore_category = understanding.restore_context_category
        if restore_category:
            if request_restore(conversation, restore_category):
                understanding = UserUnderstanding(
                    intent=UserIntent.CLARIFY,
                    confidence=understanding.confidence,
                    clarifying_question=(
                        "是否恢复之前的"
                        f"{conversation.pending_restore_display_target or restore_category}"
                        "需求？"
                    ),
                    restore_context_category=restore_category,
                )
        logger.info("agent intent understood intent=%s", understanding.intent.value)
        return {"conversation": conversation, "understanding": understanding}

    def _update_memory(self, state: ShoppingAgentState) -> dict[str, Any]:
        result = self.state_reducer.reduce(
            conversation=state["conversation"],
            understanding=state["understanding"],
            restore_command=state.get("pending_restore_command"),
        )
        return {
            "conversation": result.conversation,
            "understanding": result.understanding,
            "negative_feedback_result": result.negative_feedback_result,
            "current_turn_is_broad": result.current_turn_is_broad,
        }

    def _decide_next_action(self, state: ShoppingAgentState) -> dict[str, AgentAction]:
        return {
            "action": decide_next_action(
                state["understanding"],
                state["conversation"],
                state.get("negative_feedback_result"),
            )
        }

    def _execute_action(self, state: ShoppingAgentState) -> dict[str, ActionResult]:
        action_result = self.action_executor.execute(
            action=state["action"],
            conversation=state["conversation"],
            understanding=state["understanding"],
            negative_feedback_result=state.get("negative_feedback_result"),
        )
        return {"action_result": action_result}

    def _generate_reply(self, state: ShoppingAgentState) -> dict[str, Any]:
        action_result = state["action_result"]

        if action_result.reply_type == "negative_feedback_noop_reply":
            return {
                "reply": build_negative_feedback_noop_reply(
                    action_result.negative_feedback
                ),
                "items": action_result.items,
            }

        if action_result.reply_type == "recommendation_reply":
            target_category = state["conversation"].preferences.get("target_category")
            reply = build_recommendation_reply(
                items=action_result.items,
                negative_feedback=action_result.negative_feedback,
                current_turn_is_broad=state.get("current_turn_is_broad") is True,
                target_category=(
                    target_category if isinstance(target_category, str) else None
                ),
            )
        elif action_result.reply_type == "explain_reply":
            reply = build_explain_reply(action_result)
        elif action_result.reply_type == "compare_reply":
            reply = build_compare_reply(action_result)
        elif action_result.reply_type == "no_results_reply":
            reply = build_no_results_reply(action_result.no_results)
        elif action_result.reply_type == "tool_error_reply":
            reply = build_tool_error_reply()
        else:
            reply = build_clarify_reply(action_result.clarifying_question)

        return {"reply": reply, "items": action_result.items}

    def _finalize_response(self, state: ShoppingAgentState) -> dict[str, Any]:
        conversation = state["conversation"]

        conversation.messages.append(ChatMessage(role="assistant", content=state["reply"]))
        if state.get("persist_response", True):
            self.store.save(conversation)

        return {
            "conversation": conversation,
            "response": self.response_state_builder.build_response(
                session_id=state["session_id"],
                reply=state["reply"],
                items=state["items"],
                conversation=conversation,
                understanding=state["understanding"],
                action=state["action"],
                action_result=state["action_result"],
                negative_feedback_result=state.get("negative_feedback_result"),
            )
        }
