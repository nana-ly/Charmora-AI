from agent.memory import ConversationState


def test_purchase_preferences_merge_preserves_unknown_fields_and_cleans_dirty_values():
    from agent.state_models import PurchasePreferences

    preferences = PurchasePreferences.from_dict(
        {
            "budget": 9000,
            "focus": ["拍照"],
            "legacy_flag": {"source": "old-session"},
        }
    )

    merged = preferences.merge_updates(
        {
            "budget": True,
            "max_price": 3000,
            "preferred_brands": "苹果",
            "focus": ["拍照", "续航"],
            "new_unknown": "kept",
        }
    )

    data = merged.to_dict()

    assert data["budget"] == 9000
    assert data["max_price"] == 3000
    assert data["preferred_brands"] == ["苹果"]
    assert data["focus"] == ["拍照", "续航"]
    assert data["legacy_flag"] == {"source": "old-session"}
    assert data["new_unknown"] == "kept"


def test_negative_updates_ignores_unknown_fields_and_invalid_indexes():
    from agent.state_models import NegativeUpdates

    updates = NegativeUpdates.from_dict(
        {
            "excluded_item_indexes": [2, True, "3"],
            "excluded_item_reference": "other",
            "exclude_all_last_items": "yes",
            "excluded_brands": "苹果",
            "remove_excluded_brands": ["华为", ""],
            "unknown_command": "ignored",
        }
    )

    assert updates.to_dict() == {
        "excluded_item_indexes": [2],
        "excluded_brands": ["苹果"],
        "remove_excluded_brands": ["华为"],
    }


def test_conversation_state_preferences_model_round_trips_old_json_fields():
    state = ConversationState.model_validate(
        {
            "session_id": "old-session",
            "preferences": {
                "target_category": "手机",
                "category": "数码电子",
                "legacy_rank_hint": "keep-me",
            },
        }
    )

    model = state.preferences_model().merge_updates({"focus": "拍照"})
    state.apply_preferences_model(model)

    assert state.preferences["target_category"] == "手机"
    assert state.preferences["category"] == "数码电子"
    assert state.preferences["legacy_rank_hint"] == "keep-me"
    assert state.preferences["focus"] == ["拍照"]


def test_turn_result_state_omits_empty_fields_for_response_state():
    from agent.state_models import TurnResultState

    state = TurnResultState(
        latest_attempt_status="tool_error",
        latest_attempt_error="recommendation_failed",
        result_status="tool_error",
        tool_error="recommendation_failed",
        relax_options=[],
        result_count=0,
    )

    assert state.to_dict() == {
        "latest_attempt_status": "tool_error",
        "latest_attempt_error": "recommendation_failed",
        "result_status": "tool_error",
        "tool_error": "recommendation_failed",
        "result_count": 0,
    }
