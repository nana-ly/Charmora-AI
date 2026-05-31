"""导购 Agent 的确定性动作决策。"""

from agent.memory import ConversationState
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.understanding import AgentAction, UserIntent, UserUnderstanding


def decide_next_action(
    understanding: UserUnderstanding,
    conversation: ConversationState,
    negative_feedback: NegativeFeedbackApplicationResult | None = None,
) -> AgentAction:
    """根据用户理解、会话状态和负反馈结果选择下一步动作。"""
    if negative_feedback and negative_feedback.needs_clarification:
        return AgentAction.CLARIFY
    if negative_feedback and negative_feedback.noop:
        return AgentAction.REPLY_ONLY
    if negative_feedback and (negative_feedback.applied or negative_feedback.removed):
        if conversation.purchase_need:
            return AgentAction.RECOMMEND
        return AgentAction.CLARIFY
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
