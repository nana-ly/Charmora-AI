"""LangGraph 版导购 Agent Runner。"""

import logging
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from agent.category_rules import detect_restore_target
from agent.context_manager import (
    ConversationCommand,
    active_target_key,
    clear_pending_restore,
    confirm_restore,
    reject_restore,
    request_restore,
    reset_for_new_target,
    resolve_pending_restore,
)
from agent.memory import ConversationState, ConversationStore
from agent.negative_feedback import (
    apply_negative_feedback,
    build_negative_filters,
    filter_item_index_negative_updates_for_current_target,
    migrate_legacy_excluded_brands,
)
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.negative_feedback_rules import extract_negative_updates
from agent.policy import decide_next_action
from agent.query_builder import build_recommendation_query
from agent.reply_builder import (
    build_clarify_reply,
    build_compare_reply,
    build_explain_reply,
    build_negative_feedback_noop_reply,
    build_no_results_reply,
    build_recommendation_reply,
    build_tool_error_reply,
)
from agent.tools import CompareTool, ExplainTool, RecommendationTool
from agent.understanding import (
    ActionResult,
    AgentAction,
    LLMUserUnderstandingService,
    NoResultsSuggestion,
    UserIntent,
    UserUnderstanding,
    UserUnderstandingService,
    clarify_understanding,
)
from core.config import LLMConfig, load_app_config
from recommendation_core.data import products as catalog_products
from schemas.chat import ChatMessage, ChatResponse
from schemas.product import ProductCard
from schemas.recommend import RecommendResponse

logger = logging.getLogger(__name__)

# 这些负反馈都依赖“上一轮商品列表”，模型未显式给出目标时应沿用当前活跃目标。
ITEM_SCOPED_NEGATIVE_UPDATE_KEYS = {
    "excluded_item_indexes",
    "excluded_item_reference",
    "exclude_all_last_items",
}


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


class LangGraphAgentRunner:
    """基于 LangGraph 的多轮导购 Agent。"""

    def __init__(
        self,
        store: ConversationStore,
        recommendation_tool: RecommendationTool,
        understanding_service: UserUnderstandingService | None = None,
        llm_config: LLMConfig | None = None,
    ):
        self.store = store
        self.recommendation_tool = recommendation_tool
        self.explain_tool = ExplainTool()
        self.compare_tool = CompareTool()
        self.llm_config = llm_config or load_app_config().llm
        self.understanding_service = understanding_service or LLMUserUnderstandingService(
            config=self.llm_config
        )

        self.graph = self._build_graph()

    def run(self, session_id: str, message: str) -> ChatResponse:
        logger.info("agent run started session_id=%s", session_id)
        logger.debug("agent input message_length=%s", len(message))
        result = self.graph.invoke({"session_id": session_id, "message": message})
        logger.info("agent run completed session_id=%s", session_id)
        return result["response"]

    def _build_graph(self):
        graph = StateGraph(ShoppingAgentState)
        graph.add_node("understand_user", self._understand_user)
        graph.add_node("update_memory", self._update_memory)
        graph.add_node("decide_next_action", self._decide_next_action)
        graph.add_node("execute_action", self._execute_action)
        graph.add_node("generate_reply", self._generate_reply)
        graph.add_node("finalize_response", self._finalize_response)

        graph.add_edge(START, "understand_user")
        graph.add_edge("understand_user", "update_memory")
        graph.add_edge("update_memory", "decide_next_action")
        graph.add_edge("decide_next_action", "execute_action")
        graph.add_edge("execute_action", "generate_reply")
        graph.add_edge("generate_reply", "finalize_response")
        graph.add_edge("finalize_response", END)
        return graph.compile()

    def _understand_user(self, state: ShoppingAgentState) -> dict[str, Any]:
        conversation = self.store.get_or_create(state["session_id"])
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
        conversation = state["conversation"]
        understanding = state["understanding"]
        restore_command = state.get("pending_restore_command")
        active_key_before = active_target_key(conversation)
        active_items_before = list(conversation.last_successful_items)
        current_turn_is_broad = (
            understanding.intent == UserIntent.RECOMMEND
            and understanding.preference_updates.get("is_broad_category_request") is True
        )
        # broad 是“本轮是否泛品类推荐”的瞬时语义；细化预算/品牌时必须写回 False，避免复用上一轮 broad 文案。
        if understanding.intent in {UserIntent.RECOMMEND, UserIntent.UPDATE_PREFERENCE}:
            understanding.preference_updates["is_broad_category_request"] = (
                current_turn_is_broad
            )
        updates = understanding.preference_updates
        current_target_key = updates.get("canonical_target_key")
        if not isinstance(current_target_key, str):
            current_target_key = None
        negative_update_keys = set(understanding.negative_updates)
        if (
            current_target_key is None
            and negative_update_keys
            and negative_update_keys.issubset(ITEM_SCOPED_NEGATIVE_UPDATE_KEYS)
        ):
            current_target_key = active_key_before

        filtered_negative_updates = filter_item_index_negative_updates_for_current_target(
            understanding.negative_updates,
            current_target_key,
            active_key_before,
            active_items_before,
        )

        if restore_command == ConversationCommand.CONFIRM_RESTORE:
            restored_understanding = confirm_restore(conversation)
            conversation.last_intent = restored_understanding.intent.value
            negative_feedback_result = apply_negative_feedback(
                conversation,
                restored_understanding.negative_updates,
                catalog_products=catalog_products,
            )
            return {
                "conversation": conversation,
                "understanding": restored_understanding,
                "negative_feedback_result": negative_feedback_result,
                "current_turn_is_broad": current_turn_is_broad,
            }

        if restore_command == ConversationCommand.REJECT_RESTORE:
            reject_restore(conversation)

        canonical_target_changed = (
            current_target_key is not None
            and active_key_before is not None
            and current_target_key != active_key_before
        )
        effective_reset = canonical_target_changed or (
            understanding.reset_context and current_target_key is None
        )
        # reset_context 是旧版理解状态；标准目标变化会自行重置。
        if effective_reset:
            reset_for_new_target(conversation)

        if understanding.purchase_need:
            conversation.purchase_need = understanding.purchase_need
        if understanding.target_item_index is not None:
            conversation.target_item_index = understanding.target_item_index

        self._merge_preferences(conversation, understanding.preference_updates)
        migrate_legacy_excluded_brands(conversation)
        negative_feedback_result = apply_negative_feedback(
            conversation,
            filtered_negative_updates,
            catalog_products=catalog_products,
        )
        conversation.last_intent = understanding.intent.value
        return {
            "conversation": conversation,
            "negative_feedback_result": negative_feedback_result,
            "current_turn_is_broad": current_turn_is_broad,
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
        action = state["action"]
        conversation = state["conversation"]
        understanding = state["understanding"]
        negative_feedback = state.get("negative_feedback_result")

        if action == AgentAction.RECOMMEND:
            return {
                "action_result": self._execute_recommendation(
                    conversation,
                    negative_feedback,
                )
            }

        if action == AgentAction.EXPLAIN:
            return {
                "action_result": self._execute_explain(
                    conversation,
                    understanding.target_item_index,
                )
            }

        if action == AgentAction.COMPARE:
            return {
                "action_result": self.compare_tool.run(
                    items=conversation.last_items,
                    compare_item_indexes=understanding.compare_item_indexes,
                )
            }

        if action == AgentAction.REPLY_ONLY:
            return {
                "action_result": ActionResult(
                    action=AgentAction.REPLY_ONLY,
                    reply_type="negative_feedback_noop_reply",
                    items=[],
                    negative_feedback=negative_feedback,
                )
            }

        question = (
            negative_feedback.clarifying_question
            if negative_feedback and negative_feedback.clarifying_question
            else understanding.clarifying_question
            or "可以告诉我想买的品类、预算和最在意的点吗？"
        )
        return {
            "action_result": ActionResult(
                action=AgentAction.CLARIFY,
                reply_type="clarify_reply",
                clarifying_question=question,
                negative_feedback=negative_feedback,
            )
        }

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

    def _finalize_response(self, state: ShoppingAgentState) -> dict[str, ChatResponse]:
        conversation = state["conversation"]
        understanding = state["understanding"]
        action = state["action"]
        action_result = state["action_result"]

        conversation.messages.append(ChatMessage(role="assistant", content=state["reply"]))
        self.store.save(conversation)

        response_state: dict[str, Any] = {
            "intent": understanding.intent.value,
            "action": action.value,
            "confidence": understanding.confidence,
            "purchase_need": conversation.purchase_need,
            "preferences": conversation.preferences.copy(),
            "excluded_product_ids": list(conversation.excluded_product_ids),
            "excluded_brands": list(conversation.excluded_brands),
            "latest_attempt_status": conversation.latest_attempt_status,
        }
        negative_feedback = action_result.negative_feedback or state.get(
            "negative_feedback_result"
        )
        if negative_feedback and negative_feedback.detected:
            response_state["negative_feedback"] = negative_feedback.model_dump()
        # 只暴露本轮推荐执行状态，避免 explain 继承上一轮失败标记。
        if action_result.action == AgentAction.RECOMMEND and conversation.last_result_status:
            response_state["result_status"] = conversation.last_result_status
        if action_result.tool_error:
            response_state["tool_error"] = action_result.tool_error
        if action_result.no_results:
            response_state["relax_options"] = action_result.no_results.relax_options
        if conversation.pending_restore_category:
            response_state["pending_restore_category"] = (
                conversation.pending_restore_category
            )
        if conversation.pending_restore_display_target:
            response_state["pending_restore_display_target"] = (
                conversation.pending_restore_display_target
            )

        return {
            "response": ChatResponse(
                session_id=state["session_id"],
                reply=state["reply"],
                items=state["items"],
                state=response_state,
            )
        }

    def _execute_recommendation(
        self,
        conversation: ConversationState,
        negative_feedback: NegativeFeedbackApplicationResult | None = None,
    ) -> ActionResult:
        recommendation_query = self._build_recommendation_query(conversation)
        logger.debug("agent recommendation query_length=%s", len(recommendation_query))
        try:
            result = self.recommendation_tool.run(
                recommendation_query,
                negative_filters=build_negative_filters(conversation),
            )
        except Exception:
            return self._handle_recommendation_tool_error(
                conversation,
                recommendation_query,
                negative_feedback,
            )
        logger.info("agent recommendation completed item_count=%s", len(result.items))

        if not result.items:
            no_results = self._handle_no_results(conversation, result, recommendation_query)
            return ActionResult(
                action=AgentAction.RECOMMEND,
                reply_type="no_results_reply",
                recommendation_query=recommendation_query,
                items=[],
                no_results=no_results,
                negative_feedback=negative_feedback,
            )

        self._save_successful_recommendation(conversation, result)
        return ActionResult(
            action=AgentAction.RECOMMEND,
            reply_type="recommendation_reply",
            recommendation_query=recommendation_query,
            items=result.items,
            negative_feedback=negative_feedback,
        )

    def _execute_explain(
        self,
        conversation: ConversationState,
        target_item_index: int | None,
    ) -> ActionResult:
        result = self.explain_tool.run(
            items=conversation.last_items,
            target_item_index=target_item_index,
            fallback_item_index=conversation.target_item_index,
        )
        if result.reply_type == "explain_reply":
            conversation.target_item_index = result.target_item_index
        return result

    def _merge_preferences(
        self,
        conversation: ConversationState,
        updates: dict[str, Any],
    ) -> None:
        for key, value in updates.items():
            if value is None:
                continue
            if isinstance(value, list):
                current = conversation.preferences.get(key, [])
                if not isinstance(current, list):
                    current = []
                conversation.preferences[key] = self._merge_unique(current, value)
            else:
                conversation.preferences[key] = value

    def _merge_unique(self, current: list[Any], updates: list[Any]) -> list[Any]:
        merged: list[Any] = []
        for item in [*current, *updates]:
            if item not in merged:
                merged.append(item)
        return merged

    def _build_recommendation_query(self, conversation: ConversationState) -> str:
        return build_recommendation_query(conversation)

    def _save_successful_recommendation(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
    ) -> None:
        conversation.last_query = result.query
        conversation.last_filters = result.filters
        conversation.last_items = result.items
        conversation.latest_attempt_status = "success"
        conversation.latest_attempt_error = None
        conversation.latest_no_results_relax_options = []
        conversation.last_result_status = "success"
        conversation.last_no_results_need = None
        conversation.last_no_results_relax_options = []
        conversation.last_successful_result_id = str(uuid4())
        conversation.last_successful_query = result.query
        conversation.last_successful_filters = result.filters
        conversation.last_successful_items = result.items
        conversation.preferences.update(result.filters.model_dump(exclude_none=True))

    def _handle_no_results(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
        recommendation_query: str,
    ) -> NoResultsSuggestion:
        conversation.last_query = recommendation_query
        conversation.last_filters = result.filters
        conversation.latest_attempt_status = "no_results"
        conversation.latest_attempt_error = None
        conversation.last_result_status = "no_results"
        conversation.last_no_results_need = recommendation_query

        suggestion = NoResultsSuggestion(
            purchase_need=recommendation_query,
            blocking_constraints=self._detect_blocking_constraints(conversation, result),
            relax_options=self._build_relax_options(conversation, result),
        )
        conversation.latest_no_results_relax_options = suggestion.relax_options
        conversation.last_no_results_relax_options = suggestion.relax_options
        return suggestion

    def _handle_recommendation_tool_error(
        self,
        conversation: ConversationState,
        recommendation_query: str,
        negative_feedback: NegativeFeedbackApplicationResult | None = None,
    ) -> ActionResult:
        """推荐工具失败时保留上一轮结果，只记录本轮可恢复错误。"""
        logger.exception("agent recommendation tool failed")
        conversation.last_query = recommendation_query
        conversation.latest_attempt_status = "tool_error"
        conversation.latest_attempt_error = "recommendation_failed"
        conversation.last_result_status = "tool_error"
        return ActionResult(
            action=AgentAction.RECOMMEND,
            reply_type="tool_error_reply",
            recommendation_query=recommendation_query,
            items=[],
            tool_error="recommendation_failed",
            negative_feedback=negative_feedback,
        )

    def _detect_blocking_constraints(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
    ) -> list[str]:
        constraints: list[str] = []
        budget = conversation.preferences.get("budget")
        if budget:
            constraints.append(str(budget))
        elif result.filters.max_price is not None:
            constraints.append(f"预算{result.filters.max_price}以内")

        category = conversation.preferences.get("category") or result.filters.category
        if category:
            constraints.append(str(category))

        focus = conversation.preferences.get("focus")
        if isinstance(focus, list):
            constraints.extend(str(item) for item in focus[:3])
        elif focus:
            constraints.append(str(focus))

        return self._merge_unique([], constraints)

    def _build_relax_options(
        self,
        conversation: ConversationState,
        result: RecommendResponse,
    ) -> list[str]:
        options: list[str] = []
        if conversation.preferences.get("budget") or result.filters.max_price is not None:
            options.append("提高预算或放宽价格上限")
        if result.filters.brand or conversation.excluded_brands:
            options.append("放宽品牌限制")

        category = conversation.preferences.get("category") or result.filters.category
        if category:
            options.append("考虑相近或更宽的品类")

        focus = conversation.preferences.get("focus")
        if isinstance(focus, list) and len(focus) > 1:
            options.append("只保留最重要的一个功能重点")

        if not options:
            options = ["放宽预算", "放宽品牌或品类", "告诉我哪个条件最重要"]
        return options[:3]
