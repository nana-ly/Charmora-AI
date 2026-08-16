"""LangGraph-style shopping Agent runner.

This runner is the backend orchestration center: it keeps LLM understanding,
conversation memory, deterministic policy, tool execution, and response state
in one explicit turn pipeline.
"""

from __future__ import annotations

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
from agent.negative_feedback_rules import extract_negative_updates
from agent.policy import decide_next_action
from agent.reply_builder import (
    build_clarify_reply,
    build_commerce_reply,
    build_compare_reply,
    build_explain_reply,
    build_llm_reply,
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


class ShoppingGraphState(TypedDict, total=False):
    """Mutable state passed between LangGraph nodes for one shopping turn."""

    session_id: str
    message: str
    conversation: ConversationState
    persist_response: bool
    understanding: UserUnderstanding
    negative_feedback_result: Any
    current_turn_is_broad: bool
    pending_restore_command: ConversationCommand
    action: AgentAction
    action_result: ActionResult
    items: list[ProductCard]
    reply: str
    content_blocks: list[dict[str, Any]]
    response: ChatResponse


class LangGraphAgentRunner:
    """Multi-turn shopping Agent runner used by `/chat` and `/chat/stream`."""

    def __init__(
        self,
        store: ConversationStore,
        recommendation_tool: RecommendationTool,
        understanding_service: UserUnderstandingService | None = None,
        llm_config: LLMConfig | None = None,
        session_lock_manager: SessionLockManager | None = None,
        session_lock_enabled: bool = True,
        commerce_tool=None,
    ) -> None:
        self.store = store
        self.recommendation_tool = recommendation_tool
        self.llm_config = llm_config or load_app_config().llm
        self.understanding_service = understanding_service or LLMUserUnderstandingService(
            config=self.llm_config
        )
        self.session_lock_manager = session_lock_manager or SessionLockManager()
        self.session_lock_enabled = session_lock_enabled
        self.state_reducer = ConversationStateReducer()
        self.action_executor = ActionExecutor(
            recommendation_tool,
            commerce_tool=commerce_tool,
        )
        self.response_state_builder = ResponseStateBuilder()
        self._node_callback: Callable[[str, str, str], None] | None = None
        self.graph = self._build_graph()

    def _build_graph(self):
        """Compile the real conditional LangGraph used for every turn."""
        builder = StateGraph(ShoppingGraphState)
        builder.add_node("understand_user", self._graph_node("understand_user", self._understand_user))
        builder.add_node("update_memory", self._graph_node("update_memory", self._update_memory))
        builder.add_node(
            "decide_next_action",
            self._graph_node("decide_next_action", self._decide_next_action),
        )
        for action_name in (action.value for action in AgentAction):
            node_name = f"execute_{action_name}"
            builder.add_node(node_name, self._graph_node(node_name, self._execute_action))
            builder.add_edge(node_name, "generate_reply")
        builder.add_node("generate_reply", self._graph_node("generate_reply", self._generate_reply))
        builder.add_node(
            "finalize_response",
            self._graph_node("finalize_response", self._finalize_response),
        )

        builder.add_edge(START, "understand_user")
        builder.add_edge("understand_user", "update_memory")
        builder.add_edge("update_memory", "decide_next_action")
        builder.add_conditional_edges(
            "decide_next_action",
            self._route_action,
            {
                action.value: f"execute_{action.value}"
                for action in AgentAction
            },
        )
        builder.add_edge("generate_reply", "finalize_response")
        builder.add_edge("finalize_response", END)
        return builder.compile()

    def _graph_node(
        self,
        node: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> Callable[[ShoppingGraphState], dict[str, Any]]:
        def invoke(state: ShoppingGraphState) -> dict[str, Any]:
            return self._timed_node(node, handler, dict(state))

        return invoke

    @staticmethod
    def _route_action(state: ShoppingGraphState) -> str:
        return state["action"].value

    def run(
        self,
        session_id: str,
        message: str,
        node_callback: Callable[[str, str, str], None] | None = None,
    ) -> ChatResponse:
        self._node_callback = node_callback
        context = get_request_context()
        request_id = context.request_id if context and context.request_id != "-" else uuid4().hex
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

            logger.info(
                "agent run completed session_id=%s turn_id=%s",
                session_id,
                turn_id,
            )
            return response

    def _run_state_update(self, session_id: str, message: str) -> ChatResponse:
        if isinstance(self.store, VersionedConversationStore):
            response_holder: dict[str, ChatResponse] = {}

            def mutate(conversation: ConversationState) -> ConversationState:
                response_holder["response"], next_state = self._run_turn(
                    session_id=session_id,
                    message=message,
                    conversation=conversation,
                    persist_response=False,
                )
                return next_state

            self.store.update(session_id, mutate)
            return response_holder["response"]

        logger.warning(
            "conversation store does not support atomic update; falling back to save path"
        )
        conversation = self.store.get_or_create(session_id)
        response, _ = self._run_turn(
            session_id=session_id,
            message=message,
            conversation=conversation,
            persist_response=True,
        )
        return response

    def _run_turn(
        self,
        *,
        session_id: str,
        message: str,
        conversation: ConversationState,
        persist_response: bool,
    ) -> tuple[ChatResponse, ConversationState]:
        state: ShoppingGraphState = {
            "session_id": session_id,
            "message": message,
            "conversation": conversation,
            "persist_response": persist_response,
        }
        result = self.graph.invoke(state)
        return result["response"], result["conversation"]

    def _timed_node(
        self,
        node: str,
        handler: Callable[[dict[str, Any]], dict[str, Any]],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        self._emit("start", node)
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
        merged = {**state, **output}
        fields = self._node_log_fields(merged)
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
        self._emit("done", node, self._node_detail(node, merged))
        return output

    def _node_log_fields(self, state: dict[str, Any]) -> dict[str, Any]:
        understanding = state.get("understanding")
        action = state.get("action")
        action_result = state.get("action_result")
        items = state.get("items")
        result_count: int | str = "-"
        fallback_reason = "-"
        reply_type = getattr(action_result, "reply_type", "-") if action_result else "-"
        if action_result:
            result_count = (
                action_result.result_count
                if action_result.result_count is not None
                else len(action_result.items)
            )
            fallback_reason = self._fallback_reason(action_result)
        elif isinstance(items, list):
            result_count = len(items)
        return {
            "intent": getattr(getattr(understanding, "intent", None), "value", "-"),
            "action": getattr(action, "value", action) or "-",
            "reply_type": reply_type,
            "fallback_reason": fallback_reason,
            "result_count": result_count,
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

    def _understand_user(self, state: dict[str, Any]) -> dict[str, Any]:
        conversation: ConversationState = state["conversation"]
        message: str = state["message"]
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
        if restore_category and request_restore(conversation, restore_category):
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

    def _update_memory(self, state: dict[str, Any]) -> dict[str, Any]:
        result = self.state_reducer.reduce(
            conversation=state["conversation"],
            understanding=state["understanding"],
            restore_command=state.get("pending_restore_command")
            or ConversationCommand.NONE,
        )
        return {
            "conversation": result.conversation,
            "understanding": result.understanding,
            "negative_feedback_result": result.negative_feedback_result,
            "current_turn_is_broad": result.current_turn_is_broad,
        }

    def _decide_next_action(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "action": decide_next_action(
                state["understanding"],
                state["conversation"],
                state.get("negative_feedback_result"),
            )
        }

    def _execute_action(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "action_result": self.action_executor.execute(
                action=state["action"],
                conversation=state["conversation"],
                understanding=state["understanding"],
                negative_feedback_result=state.get("negative_feedback_result"),
            )
        }

    def _generate_reply(self, state: dict[str, Any]) -> dict[str, Any]:
        action: AgentAction = state["action"]
        action_result: ActionResult = state["action_result"]
        content_blocks: list[dict[str, Any]] = []

        if action_result.reply_type == "negative_feedback_noop_reply":
            reply = build_negative_feedback_noop_reply(action_result.negative_feedback)
        elif action_result.reply_type == "recommendation_reply":
            reply, content_blocks = self._build_recommendation_text(state)
        elif action_result.reply_type == "explain_reply":
            reply = build_explain_reply(action_result)
        elif action_result.reply_type == "compare_reply":
            reply = build_compare_reply(action_result)
        elif action_result.reply_type == "no_results_reply":
            reply = build_no_results_reply(action_result.no_results)
        elif action_result.reply_type == "tool_error_reply":
            reply = build_tool_error_reply()
        elif action_result.reply_type in {
            "cart_reply",
            "cart_updated_reply",
            "order_created_reply",
            "order_status_reply",
            "order_cancelled_reply",
            "commerce_error_reply",
        }:
            reply = build_commerce_reply(
                action_result.reply_type,
                action_result.commerce_state,
            )
        else:
            reply = build_clarify_reply(action_result.clarifying_question)

        return {
            "reply": reply,
            "items": action_result.items,
            "content_blocks": content_blocks,
            "action": action,
        }

    def _build_recommendation_text(
        self,
        state: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]]]:
        action_result: ActionResult = state["action_result"]
        conversation: ConversationState = state["conversation"]
        try:
            return build_llm_reply(
                action_result=action_result,
                action=state["action"],
                purchase_need=conversation.purchase_need,
                messages=conversation.messages,
                preferences=conversation.preferences,
                llm_config=self.llm_config,
            )
        except Exception:
            logger.debug("llm reply generation unavailable; using deterministic reply")

        target_category = conversation.preferences.get("target_category")
        return (
            build_recommendation_reply(
                items=action_result.items,
                negative_feedback=action_result.negative_feedback,
                current_turn_is_broad=state.get("current_turn_is_broad") is True,
                target_category=target_category if isinstance(target_category, str) else None,
            ),
            [],
        )

    def _finalize_response(self, state: dict[str, Any]) -> dict[str, Any]:
        conversation: ConversationState = state["conversation"]
        conversation.messages.append(ChatMessage(role="assistant", content=state["reply"]))
        if state.get("persist_response", True):
            self.store.save(conversation)

        response = self.response_state_builder.build_response(
            session_id=state["session_id"],
            reply=state["reply"],
            items=state["items"],
            conversation=conversation,
            understanding=state["understanding"],
            action=state["action"],
            action_result=state["action_result"],
            negative_feedback_result=state.get("negative_feedback_result"),
            content_blocks=state.get("content_blocks") or [],
        )
        return {"conversation": conversation, "response": response}

    def _node_detail(self, node: str, state: dict[str, Any]) -> str:
        if node == "understand_user" and state.get("understanding"):
            return f"识别意图：{state['understanding'].intent.value}"
        if node == "decide_next_action" and state.get("action"):
            return f"选择动作：{state['action'].value}"
        if node == "execute_action" and state.get("action_result"):
            result = state["action_result"]
            count = result.result_count if result.result_count is not None else len(result.items)
            return f"工具结果：{result.reply_type}，候选 {count} 个"
        if node == "generate_reply":
            return "生成导购回复"
        return node

    def _emit(self, event: str, node: str, detail: str = "") -> None:
        if self._node_callback:
            self._node_callback(event, node, detail)
