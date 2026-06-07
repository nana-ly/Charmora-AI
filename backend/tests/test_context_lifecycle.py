def test_context_transition_records_switch_target():
    from agent.context_lifecycle import ContextTransition, ContextTransitionType

    transition = ContextTransition(
        type=ContextTransitionType.SWITCH_TARGET,
        from_target_key="phone",
        to_target_key="skin_care",
        reason="target_changed",
    )

    assert transition.type == ContextTransitionType.SWITCH_TARGET
    assert transition.from_target_key == "phone"
    assert transition.to_target_key == "skin_care"


def test_switch_target_with_transition_archives_previous_context():
    from agent.context_lifecycle import switch_target_with_transition
    from agent.memory import ConversationState

    conversation = ConversationState(
        session_id="lifecycle",
        purchase_need="预算9000以内的手机",
        preferences={
            "target_category": "手机",
            "category": "数码电子",
            "canonical_target_key": "phone",
        },
    )

    transition = switch_target_with_transition(
        conversation,
        new_target_key="skin_care",
        reason="target_changed",
    )

    assert transition.from_target_key == "phone"
    assert transition.to_target_key == "skin_care"
    assert transition.archived_context_id == "phone"
    assert len(conversation.previous_purchase_contexts) == 1
    assert conversation.purchase_need is None
