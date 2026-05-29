from agent.memory import ConversationState
from agent.negative_feedback import (
    apply_negative_feedback,
    migrate_legacy_excluded_brands,
)
from agent.negative_feedback_rules import extract_negative_updates
from schemas.product import ProductCard


def make_phone_state() -> ConversationState:
    state = ConversationState(session_id="session-negative-apply")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}
    state.last_successful_items = [
        ProductCard(
            product_id="p_apple",
            title="苹果拍照手机",
            brand="苹果",
            price=8999,
            reason="适合拍照。",
            evidence="命中拍照。",
        ),
        ProductCard(
            product_id="p_huawei",
            title="华为拍照手机",
            brand="华为",
            price=5999,
            reason="适合拍照。",
            evidence="命中拍照。",
        ),
    ]
    state.last_items = list(state.last_successful_items)
    state.last_successful_result_id = "result-1"
    return state


def test_negative_rules_detect_arabic_item_index_exclusion():
    assert extract_negative_updates("不要第 2 个") == {"excluded_item_indexes": [2]}
    assert extract_negative_updates("排除第2款") == {"excluded_item_indexes": [2]}
    assert extract_negative_updates("第 3 个不要") == {"excluded_item_indexes": [3]}
    assert extract_negative_updates("不要第2个也可以") == {"excluded_item_indexes": [2]}


def test_negative_rules_do_not_parse_chinese_item_index():
    assert extract_negative_updates("排除第二款") == {
        "unsupported_negative_type": "item_index_chinese_number"
    }


def test_negative_rules_detect_brand_exclusion_and_removal_text():
    assert extract_negative_updates("不要苹果") == {"excluded_brands": ["苹果"]}
    assert extract_negative_updates("不考虑华为") == {"excluded_brands": ["华为"]}
    assert extract_negative_updates("苹果也可以") == {"remove_excluded_brands": ["苹果"]}
    assert extract_negative_updates("取消排除苹果") == {"remove_excluded_brands": ["苹果"]}


def test_negative_rules_brand_exclusion_wins_for_ambiguous_removal_text():
    assert extract_negative_updates("不要苹果也可以") == {"excluded_brands": ["苹果"]}
    assert extract_negative_updates("苹果也可以不要") == {"excluded_brands": ["苹果"]}


def test_extract_negative_updates_single_field_priority_for_mixed_item_index_and_brand():
    from agent.negative_feedback_rules import extract_negative_updates

    assert extract_negative_updates("推荐手机，不要第2个，不要苹果") == {
        "excluded_item_indexes": [2]
    }


def test_clean_positive_purchase_need_removes_all_negative_phrases_with_single_field_updates():
    from agent.negative_feedback_rules import (
        clean_positive_purchase_need,
        extract_negative_updates,
    )

    message = "推荐手机，不要第2个，不要苹果"
    negative_updates = extract_negative_updates(message)

    cleaned = clean_positive_purchase_need(message, negative_updates)

    assert cleaned == "推荐手机"
    assert "不要第2个" not in cleaned
    assert "不要苹果" not in cleaned


def test_clean_positive_purchase_need_allows_empty_string_for_pure_negative_text():
    from agent.negative_feedback_rules import clean_positive_purchase_need

    assert clean_positive_purchase_need("不要苹果") == ""


def test_clean_positive_purchase_need_preserves_cancel_or_remove_negative_updates():
    from agent.negative_feedback_rules import (
        clean_positive_purchase_need,
        extract_negative_updates,
    )

    message = "取消排除苹果"
    updates = extract_negative_updates(message)

    assert updates == {"remove_excluded_brands": ["苹果"]}
    assert clean_positive_purchase_need(message, updates) == message


def test_clean_positive_purchase_need_removes_avoid_brand_markers():
    from agent.negative_feedback_rules import clean_positive_purchase_need

    assert clean_positive_purchase_need("推荐手机，避开苹果") == "推荐手机"
    assert clean_positive_purchase_need("推荐手机，别要苹果") == "推荐手机"


def test_negative_rules_do_not_treat_price_feedback_as_brand_exclusion():
    assert extract_negative_updates("苹果手机不要这么贵") == {}


def test_negative_rules_mark_item_removal_as_unsupported_for_mvp():
    assert extract_negative_updates("第 2 个也可以") == {
        "remove_excluded_item_indexes": [2],
        "unsupported_negative_type": "remove_item_index",
    }


def test_apply_negative_feedback_excludes_item_by_last_successful_index():
    state = make_phone_state()

    result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": [2]},
        catalog_products=[],
    )

    assert result.applied is True
    assert result.target_product_ids == ["p_huawei"]
    assert state.excluded_product_ids == ["p_huawei"]
    assert result.ack_message == "已排除第 2 款，我按你的需求重新筛选。"


def test_apply_negative_feedback_keeps_mvp_item_index_priority_for_mixed_updates():
    state = make_phone_state()

    result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": [2], "excluded_brands": ["苹果"]},
        catalog_products=[],
    )

    assert result.applied is True
    assert result.target_product_ids == ["p_huawei"]
    assert state.excluded_product_ids == ["p_huawei"]
    assert state.excluded_brands == []


def test_apply_negative_feedback_duplicate_item_is_noop_without_audit_mutation():
    state = make_phone_state()
    first_result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": [2]},
        catalog_products=[],
    )
    audit_count = len(state.negative_feedback_items)

    second_result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": [2]},
        catalog_products=[],
    )

    assert first_result.applied is True
    assert second_result.noop is True
    assert second_result.noop_reason == "already_excluded"
    assert state.excluded_product_ids == ["p_huawei"]
    assert len(state.negative_feedback_items) == audit_count


def test_apply_negative_feedback_invalid_index_clarifies_without_mutation():
    state = make_phone_state()

    result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": [5]},
        catalog_products=[],
    )

    assert result.needs_clarification is True
    assert result.applied is False
    assert result.clarifying_question == "上一轮只有 2 款商品，你想排除第几款？"
    assert state.excluded_product_ids == []
    assert state.negative_feedback_items == []


def test_apply_negative_feedback_empty_item_index_clarifies_without_mutation():
    state = make_phone_state()

    result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": []},
        catalog_products=[],
    )

    assert result.detected is True
    assert result.needs_clarification is True
    assert result.applied is False
    assert result.invalid_reason == "missing_item_index"
    assert state.excluded_product_ids == []


def test_apply_negative_feedback_missing_last_items_clarifies_without_mutation():
    state = ConversationState(session_id="session-negative-no-items")

    result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": [1]},
        catalog_products=[],
    )

    assert result.detected is True
    assert result.needs_clarification is True
    assert result.invalid_reason == "missing_last_successful_items"
    assert result.clarifying_question == (
        "我还没有上一轮可排除的推荐结果，可以先告诉我想买什么。"
    )
    assert state.excluded_product_ids == []


def test_apply_negative_feedback_bool_item_index_clarifies_without_mutation():
    state = make_phone_state()

    result = apply_negative_feedback(
        state,
        {"excluded_item_indexes": [True]},
        catalog_products=[],
    )

    assert result.needs_clarification is True
    assert result.invalid_reason == "missing_item_index"
    assert state.excluded_product_ids == []


def test_apply_negative_feedback_excludes_authoritative_brand():
    state = make_phone_state()

    result = apply_negative_feedback(
        state,
        {"excluded_brands": [" 苹果 "]},
        catalog_products=[],
    )

    assert result.applied is True
    assert result.target_brands == ["苹果"]
    assert state.excluded_brands == ["苹果"]
    assert result.ack_message == "已排除苹果，我按你的需求重新筛选。"


def test_apply_negative_feedback_rejects_unknown_brand():
    state = make_phone_state()

    result = apply_negative_feedback(
        state,
        {"excluded_brands": ["曲面屏"]},
        catalog_products=[],
    )

    assert result.needs_clarification is True
    assert result.noop is False
    assert result.invalid_reason == "unknown_brand"
    assert state.excluded_brands == []


def test_apply_negative_feedback_without_purchase_context_clarifies_brand_scope():
    state = ConversationState(session_id="session-negative-apply-empty")

    result = apply_negative_feedback(
        state,
        {"excluded_brands": ["苹果"]},
        catalog_products=[{"brand": "苹果"}],
    )

    assert result.needs_clarification is True
    assert result.applied is False
    assert state.excluded_brands == []
    assert result.clarifying_question == "可以，想买什么品类时排除苹果？"


def test_apply_negative_feedback_removes_existing_brand_and_cleans_preferences():
    state = make_phone_state()
    state.excluded_brands = ["苹果"]
    state.preferences["brand"] = "苹果"
    state.preferences["preferred_brands"] = ["苹果", "华为"]
    state.preferences["excluded_brands"] = ["苹果"]

    result = apply_negative_feedback(
        state,
        {"remove_excluded_brands": ["苹果"]},
        catalog_products=[],
    )

    assert result.removed is True
    assert state.excluded_brands == []
    assert "brand" not in state.preferences
    assert state.preferences["preferred_brands"] == ["华为"]
    assert "excluded_brands" not in state.preferences


def test_apply_negative_feedback_duplicate_brand_is_noop():
    state = make_phone_state()
    state.excluded_brands = ["苹果"]

    result = apply_negative_feedback(
        state,
        {"excluded_brands": ["苹果"]},
        catalog_products=[],
    )

    assert result.noop is True
    assert result.noop_reason == "already_excluded"
    assert state.excluded_brands == ["苹果"]


def test_apply_negative_feedback_duplicate_brand_from_existing_state_is_noop_without_catalog_match():
    state = make_phone_state()
    state.last_successful_items = []
    state.last_items = []
    state.excluded_brands = ["苹果"]

    result = apply_negative_feedback(
        state,
        {"excluded_brands": ["苹果"]},
        catalog_products=[],
    )

    assert result.noop is True
    assert result.noop_reason == "already_excluded"
    assert result.invalid_reason is None
    assert state.excluded_brands == ["苹果"]


def test_migrate_legacy_excluded_brands_pops_preference_key():
    state = ConversationState(session_id="session-negative-legacy")
    state.preferences = {"excluded_brands": ["苹果"], "focus": ["拍照"]}

    migrate_legacy_excluded_brands(state)

    assert state.excluded_brands == ["苹果"]
    assert state.preferences == {"focus": ["拍照"]}


def test_filter_item_index_negative_updates_drops_indexes_before_apply_negative_feedback():
    from agent.negative_feedback import filter_item_index_negative_updates_for_current_target
    from schemas.product import ProductCard

    items = [
        ProductCard(
            product_id="p_phone_1",
            title="手机1",
            brand="BrandA",
            price=1000,
            reason="test",
            evidence="test",
        )
    ]

    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_item_indexes": [1]},
        current_target_key="headphones",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {}
    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_item_indexes": [2], "excluded_brands": ["苹果"]},
        current_target_key="headphones",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {"excluded_brands": ["苹果"]}
    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_brands": ["苹果"]},
        current_target_key="phone",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {"excluded_brands": ["苹果"]}
    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_item_indexes": [1]},
        current_target_key="phone",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {"excluded_item_indexes": [1]}
    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_item_indexes": [2]},
        current_target_key=None,
        active_target_key=None,
        active_last_successful_items=items,
    ) == {"excluded_item_indexes": [2]}
    assert filter_item_index_negative_updates_for_current_target(
        {"excluded_item_indexes": [1], "excluded_brands": ["苹果"]},
        current_target_key="phone",
        active_target_key="phone",
        active_last_successful_items=items,
    ) == {"excluded_item_indexes": [1], "excluded_brands": ["苹果"]}
