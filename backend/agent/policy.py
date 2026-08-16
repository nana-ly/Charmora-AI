"""Deterministic action policy for the shopping Agent."""

from agent.memory import ConversationState
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.understanding import AgentAction, UserIntent, UserUnderstanding


def decide_next_action(
    understanding: UserUnderstanding,
    conversation: ConversationState,
    negative_feedback: NegativeFeedbackApplicationResult | None = None,
) -> AgentAction:
    """Choose the next tool/action from structured understanding and memory."""
    commerce_actions = {
        UserIntent.ADD_TO_CART: AgentAction.ADD_TO_CART,
        UserIntent.VIEW_CART: AgentAction.VIEW_CART,
        UserIntent.CHECKOUT: AgentAction.CHECKOUT,
        UserIntent.ORDER_STATUS: AgentAction.ORDER_STATUS,
        UserIntent.CANCEL_ORDER: AgentAction.CANCEL_ORDER,
    }
    if understanding.intent in commerce_actions:
        return commerce_actions[understanding.intent]

    if negative_feedback and negative_feedback.needs_clarification:
        return AgentAction.CLARIFY
    if negative_feedback and negative_feedback.noop:
        return AgentAction.REPLY_ONLY
    if negative_feedback and (negative_feedback.applied or negative_feedback.removed):
        return AgentAction.RECOMMEND if conversation.purchase_need else AgentAction.CLARIFY
    if negative_feedback and negative_feedback.detected and not conversation.purchase_need:
        return AgentAction.CLARIFY

    if understanding.intent == UserIntent.EXPLAIN:
        return AgentAction.EXPLAIN
    if understanding.intent == UserIntent.COMPARE:
        return AgentAction.COMPARE
    if understanding.intent == UserIntent.CLARIFY:
        return AgentAction.CLARIFY
    if conversation.purchase_need:
        return AgentAction.RECOMMEND
    return AgentAction.CLARIFY
