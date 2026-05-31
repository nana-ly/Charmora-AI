from agent.memory import ConversationState
from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.understanding import ActionResult, AgentAction, UserIntent, UserUnderstanding
from schemas.product import ProductCard


def test_response_state_builder_exposes_recommend_success_fields():
    from agent.graph.response_state_builder import ResponseStateBuilder

    item = ProductCard(
        product_id="p1",
        title="拍照手机",
        brand="小米",
        price=3999,
        reason="拍照不错",
        evidence="命中拍照",
    )
    conversation = ConversationState(session_id="builder-success")
    conversation.purchase_need = "手机"
    conversation.preferences = {"target_category": "手机", "category": "数码电子"}
    conversation.latest_attempt_status = "success"
    conversation.last_result_status = "success"
    negative_feedback = NegativeFeedbackApplicationResult(detected=True, applied=True)
    action_result = ActionResult(
        action=AgentAction.RECOMMEND,
        reply_type="recommendation_reply",
        items=[item],
        negative_feedback=negative_feedback,
    )
    understanding = UserUnderstanding(intent=UserIntent.RECOMMEND, confidence=0.9)

    response = ResponseStateBuilder().build_response(
        session_id="builder-success",
        reply="给你推荐这款。",
        items=[item],
        conversation=conversation,
        understanding=understanding,
        action=AgentAction.RECOMMEND,
        action_result=action_result,
    )

    assert response.state["intent"] == "recommend"
    assert response.state["action"] == "recommend"
    assert response.state["result_status"] == "success"
    assert response.state["negative_feedback"]["applied"] is True


def test_response_state_builder_exposes_no_results_and_tool_error_selectively():
    from agent.graph.response_state_builder import ResponseStateBuilder
    from agent.understanding import NoResultsSuggestion

    conversation = ConversationState(session_id="builder-no-results")
    conversation.latest_attempt_status = "no_results"
    conversation.last_result_status = "no_results"
    action_result = ActionResult(
        action=AgentAction.RECOMMEND,
        reply_type="no_results_reply",
        no_results=NoResultsSuggestion(
            purchase_need="严格手机需求",
            relax_options=["提高预算"],
        ),
    )
    understanding = UserUnderstanding(intent=UserIntent.RECOMMEND, confidence=0.8)

    response = ResponseStateBuilder().build_response(
        session_id="builder-no-results",
        reply="暂时没找到。",
        items=[],
        conversation=conversation,
        understanding=understanding,
        action=AgentAction.RECOMMEND,
        action_result=action_result,
    )

    assert response.state["result_status"] == "no_results"
    assert response.state["relax_options"] == ["提高预算"]
    assert "tool_error" not in response.state


def test_response_state_builder_does_not_leak_stale_result_status_for_explain():
    from agent.graph.response_state_builder import ResponseStateBuilder

    conversation = ConversationState(session_id="builder-explain")
    conversation.latest_attempt_status = "tool_error"
    conversation.last_result_status = "tool_error"
    action_result = ActionResult(
        action=AgentAction.EXPLAIN,
        reply_type="explain_reply",
        items=[],
    )
    understanding = UserUnderstanding(intent=UserIntent.EXPLAIN, confidence=0.8)

    response = ResponseStateBuilder().build_response(
        session_id="builder-explain",
        reply="解释上一轮商品。",
        items=[],
        conversation=conversation,
        understanding=understanding,
        action=AgentAction.EXPLAIN,
        action_result=action_result,
    )

    assert response.state["latest_attempt_status"] == "tool_error"
    assert "result_status" not in response.state
    assert "tool_error" not in response.state


def test_response_state_builder_only_exposes_pending_restore_when_present():
    from agent.graph.response_state_builder import ResponseStateBuilder

    conversation = ConversationState(session_id="builder-pending")
    understanding = UserUnderstanding(intent=UserIntent.CLARIFY, confidence=0.8)
    action_result = ActionResult(action=AgentAction.CLARIFY, reply_type="clarify_reply")

    response_without_pending = ResponseStateBuilder().build_response(
        session_id="builder-pending",
        reply="需要确认。",
        items=[],
        conversation=conversation,
        understanding=understanding,
        action=AgentAction.CLARIFY,
        action_result=action_result,
    )

    conversation.pending_restore_category = "phone"
    conversation.pending_restore_display_target = "手机"
    response_with_pending = ResponseStateBuilder().build_response(
        session_id="builder-pending",
        reply="需要确认。",
        items=[],
        conversation=conversation,
        understanding=understanding,
        action=AgentAction.CLARIFY,
        action_result=action_result,
    )

    assert "pending_restore_category" not in response_without_pending.state
    assert response_with_pending.state["pending_restore_category"] == "phone"
    assert response_with_pending.state["pending_restore_display_target"] == "手机"
