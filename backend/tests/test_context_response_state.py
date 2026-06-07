def test_response_state_includes_context_memory_and_result_sections():
    from agent.graph.response_state_builder import ResponseStateBuilder
    from agent.memory import ConversationState
    from agent.understanding import (
        ActionResult,
        AgentAction,
        UserIntent,
        UserUnderstanding,
    )

    conversation = ConversationState(
        session_id="structured-state",
        purchase_need="预算9000以内的手机",
        preferences={
            "target_category": "手机",
            "category": "数码电子",
            "canonical_target_key": "phone",
            "budget": 9000,
        },
        excluded_brands=["苹果"],
        latest_attempt_status="success",
        last_successful_result_id="result-1",
        last_result_status="success",
    )
    understanding = UserUnderstanding(
        intent=UserIntent.RECOMMEND,
        confidence=0.8,
        purchase_need="预算9000以内的手机",
    )
    action_result = ActionResult(
        action=AgentAction.RECOMMEND,
        reply_type="recommendation_reply",
        items=[],
        result_count=0,
    )

    response = ResponseStateBuilder().build_response(
        session_id="structured-state",
        reply="我根据你的需求筛选了这几款商品。",
        items=[],
        conversation=conversation,
        understanding=understanding,
        action=AgentAction.RECOMMEND,
        action_result=action_result,
    )

    assert response.state["context"] == {
        "active_target_key": "phone",
        "target_category": "手机",
        "category": "数码电子",
        "pending_restore": False,
        "pending_restore_category": None,
        "pending_restore_display_target": None,
    }
    assert response.state["memory"]["last_successful_result_id"] == "result-1"
    assert response.state["memory"]["archived_context_count"] == 0
    assert response.state["negative_feedback_state"]["excluded_brands"] == ["苹果"]
    assert response.state["result"]["status"] == "success"
    assert response.state["purchase_need"] == "预算9000以内的手机"
    assert response.state["preferences"]["budget"] == 9000
    assert response.state["excluded_brands"] == ["苹果"]
    assert response.state["latest_attempt_status"] == "success"
