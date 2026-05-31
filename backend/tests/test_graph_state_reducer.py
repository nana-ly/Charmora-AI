from agent.context_manager import ConversationCommand
from agent.memory import ConversationState, PurchaseContext
from agent.understanding import UserIntent, UserUnderstanding
from schemas.product import ProductCard


def make_understanding(
    *,
    intent: UserIntent,
    purchase_need: str | None = None,
    preference_updates: dict | None = None,
    negative_updates: dict | None = None,
    reset_context: bool = False,
) -> UserUnderstanding:
    return UserUnderstanding(
        intent=intent,
        confidence=0.9,
        purchase_need=purchase_need,
        preference_updates=preference_updates or {},
        negative_updates=negative_updates or {},
        reset_context=reset_context,
    )


def test_state_reducer_tracks_broad_turn_and_clears_stale_broad_flag():
    from agent.graph.state_reducer import ConversationStateReducer

    conversation = ConversationState(session_id="reducer-broad")
    reducer = ConversationStateReducer()

    first = reducer.reduce(
        conversation=conversation,
        understanding=make_understanding(
            intent=UserIntent.RECOMMEND,
            purchase_need="推荐手机",
            preference_updates={
                "target_category": "手机",
                "category": "数码电子",
                "canonical_target_key": "phone",
                "is_broad_category_request": True,
            },
        ),
    )
    second = reducer.reduce(
        conversation=conversation,
        understanding=make_understanding(
            intent=UserIntent.UPDATE_PREFERENCE,
            preference_updates={"budget": 3000},
        ),
    )

    assert first.current_turn_is_broad is True
    assert second.current_turn_is_broad is False
    assert conversation.preferences["is_broad_category_request"] is False
    assert conversation.preferences["budget"] == 3000


def test_state_reducer_confirm_restore_restores_archived_context():
    from agent.graph.state_reducer import ConversationStateReducer

    archived_source = ConversationState(session_id="archived")
    archived_source.purchase_need = "预算9000以内的手机"
    archived_source.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
    }

    conversation = ConversationState(session_id="restore")
    conversation.purchase_need = "办公室咖啡"
    conversation.preferences = {
        "target_category": "咖啡",
        "category": "食品生活",
        "canonical_target_key": "coffee",
    }
    conversation.previous_purchase_contexts = [
        PurchaseContext.from_conversation(archived_source)
    ]
    conversation.pending_restore_category = "phone"
    conversation.pending_restore_display_target = "手机"

    result = ConversationStateReducer().reduce(
        conversation=conversation,
        understanding=make_understanding(intent=UserIntent.CLARIFY),
        restore_command=ConversationCommand.CONFIRM_RESTORE,
    )

    assert result.understanding.intent == UserIntent.RECOMMEND
    assert conversation.purchase_need == "预算9000以内的手机"
    assert conversation.preferences["canonical_target_key"] == "phone"
    assert conversation.pending_restore_category is None


def test_state_reducer_filters_item_scoped_negative_updates_when_target_switches():
    from agent.graph.state_reducer import ConversationStateReducer

    conversation = ConversationState(session_id="target-switch")
    conversation.purchase_need = "手机"
    conversation.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
    }
    conversation.last_successful_items = [
        ProductCard(
            product_id="phone-1",
            title="手机 1",
            brand="苹果",
            price=5999,
            reason="拍照好",
            evidence="拍照",
        )
    ]

    result = ConversationStateReducer().reduce(
        conversation=conversation,
        understanding=make_understanding(
            intent=UserIntent.RECOMMEND,
            purchase_need="推荐护肤品",
            preference_updates={
                "target_category": "护肤品",
                "category": "美妆护肤",
                "canonical_target_key": "skin_care",
            },
            negative_updates={"excluded_item_indexes": [1]},
        ),
    )

    assert result.negative_feedback_result.detected is False
    assert conversation.excluded_product_ids == []
    assert conversation.preferences["canonical_target_key"] == "skin_care"
