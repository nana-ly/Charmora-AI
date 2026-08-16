"""对外 ChatResponse 状态构造器。"""

from __future__ import annotations

from typing import Any

from agent.memory import ConversationState
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.understanding import ActionResult, AgentAction, UserUnderstanding
from schemas.chat import ChatResponse
from schemas.product import ProductCard


def _response_active_target_key(conversation: ConversationState) -> str | None:
    """只读推导响应里的目标 key，避免构造 response 时隐藏修改会话状态。"""
    key = conversation.preferences.get("canonical_target_key")
    if isinstance(key, str) and key.strip():
        return key
    target = conversation.preferences.get("target_category")
    if isinstance(target, str) and target.strip():
        return target
    category = conversation.preferences.get("category")
    if isinstance(category, str) and category.strip():
        return category
    return None


class ResponseStateBuilder:
    """纯构造 response，不保存会话，避免隐藏存储副作用。"""

    def build_response(
        self,
        *,
        session_id: str,
        reply: str,
        items: list[ProductCard],
        conversation: ConversationState,
        understanding: UserUnderstanding,
        action: AgentAction,
        action_result: ActionResult,
        negative_feedback_result: NegativeFeedbackApplicationResult | None = None,
        content_blocks: list[dict[str, Any]] | None = None,
    ) -> ChatResponse:
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
        response_state["context"] = {
            "active_target_key": _response_active_target_key(conversation),
            "target_category": conversation.preferences.get("target_category"),
            "category": conversation.preferences.get("category"),
            "pending_restore": conversation.pending_restore_category is not None,
            "pending_restore_category": conversation.pending_restore_category,
            "pending_restore_display_target": conversation.pending_restore_display_target,
        }
        response_state["memory"] = {
            "archived_context_count": len(conversation.previous_purchase_contexts),
            "last_successful_result_id": conversation.last_successful_result_id,
        }
        response_state["negative_feedback_state"] = {
            "excluded_product_ids": list(conversation.excluded_product_ids),
            "excluded_brands": list(conversation.excluded_brands),
        }
        response_state["result"] = {
            "status": (
                conversation.last_result_status
                if action_result.action == AgentAction.RECOMMEND
                else None
            ),
            "tool_error": action_result.tool_error,
            "relax_options": (
                action_result.no_results.relax_options
                if action_result.no_results
                else []
            ),
        }
        negative_feedback = (
            action_result.negative_feedback or negative_feedback_result
        )
        if negative_feedback and negative_feedback.detected:
            response_state["negative_feedback"] = negative_feedback.model_dump()
        if action_result.commerce_state is not None:
            response_state["commerce"] = action_result.commerce_state

        # 只暴露本轮推荐执行状态，避免 explain/compare 继承上一轮失败标记。
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

        return ChatResponse(
            session_id=session_id,
            reply=reply,
            result_count=(
                action_result.result_count
                if action_result.result_count is not None
                else len(items)
            ),
            items=items,
            state=response_state,
            content_blocks=content_blocks or [],
        )
