import json

import pytest

from agent.memory import ConversationState, InMemoryConversationStore
from agent.tools import RecommendationTool
from core.config import AppConfig, LLMConfig, load_app_config
from llm.client import ChatInvokeResponse
from schemas.product import ProductCard


class FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def invoke(self, messages, max_tokens=160):
        self.calls.append({"messages": messages, "max_tokens": max_tokens})
        return ChatInvokeResponse(content=self.content)


class FakeUnderstandingService:
    def __init__(self, understandings):
        self.understandings = list(understandings)
        self.calls = []

    def understand(self, *, message, conversation):
        self.calls.append({"message": message, "conversation": conversation})
        if len(self.understandings) == 1:
            return self.understandings[0]
        return self.understandings.pop(0)


def make_understanding(
    *,
    intent,
    purchase_need=None,
    preference_updates=None,
    target_item_index=None,
    clarifying_question=None,
    confidence=0.9,
    reset_context=False,
    restore_context_category=None,
):
    from agent.understanding import UserUnderstanding

    return UserUnderstanding(
        intent=intent,
        confidence=confidence,
        purchase_need=purchase_need,
        preference_updates=preference_updates or {},
        target_item_index=target_item_index,
        clarifying_question=clarifying_question,
        reset_context=reset_context,
        restore_context_category=restore_context_category,
    )


def empty_recommendation(query: str, top_k: int = 3):
    return {
        "query": query,
        "filters": {
            "category": "数码电子",
            "max_price": 3000,
            "brand": None,
            "keywords": ["手机", "拍照", "折叠屏"],
        },
        "items": [],
    }


def single_recommendation(query: str, top_k: int = 3):
    return {
        "query": query,
        "filters": {
            "category": "数码电子",
            "max_price": 9000,
            "brand": None,
            "keywords": ["手机", "拍照"],
        },
        "items": [
            {
                "product_id": "p_test_1",
                "title": "测试拍照手机",
                "brand": "TestBrand",
                "price": 6999,
                "reason": "适合拍照需求。",
                "evidence": "命中关键词：拍照",
            }
        ][:top_k],
    }


def test_category_rules_detect_target_category_and_catalog_category():
    from agent.category_rules import catalog_category_for, detect_target_category

    phone = detect_target_category("想买一台华为手机")
    coffee = detect_target_category("办公室喝的咖啡")

    assert phone is not None
    assert phone.target_category == "手机"
    assert phone.catalog_category == "数码电子"
    assert coffee is not None
    assert coffee.target_category == "咖啡"
    assert coffee.catalog_category == "食品生活"
    assert detect_target_category("拍照和续航好一点") is None
    assert catalog_category_for("手机") == "数码电子"


def test_category_rules_detect_restore_confirmation_and_rejection():
    from agent.category_rules import is_restore_confirmation, is_restore_rejection

    assert is_restore_confirmation("对，就按之前的")
    assert is_restore_confirmation("是的，恢复之前那个手机需求")
    assert is_restore_rejection("不是，不用之前的")
    assert is_restore_rejection("不用了，预算3000以内就行")
    assert not is_restore_confirmation("不是，预算3000以内就行")


def test_category_rules_restore_confirmation_stays_narrow():
    from agent.category_rules import is_restore_confirmation

    assert not is_restore_confirmation("我对手机拍照要求高")
    assert not is_restore_confirmation("这个可以便宜点吗")
    assert is_restore_confirmation("对")
    assert is_restore_confirmation("是的")
    assert is_restore_confirmation("可以")
    assert is_restore_confirmation("对，就按之前的")
    assert is_restore_confirmation("可以，恢复之前的手机需求")


def test_category_rules_detect_purchase_signals():
    from agent.category_rules import has_purchase_signal

    assert has_purchase_signal("我想买一台手机")
    assert has_purchase_signal("预算6000以内")
    assert not has_purchase_signal("拍照和续航好一点")


def test_category_rules_extract_preference_hints():
    from agent.category_rules import extract_preference_hints

    hints = extract_preference_hints("想买华为手机，预算6000以内，主要拍照和续航，不要苹果")

    assert hints["budget"] == 6000
    assert hints["brand"] == "华为"
    assert hints["focus"] == ["拍照", "续航"]
    assert "excluded_brands" not in hints


def test_fallback_understanding_recommends_complete_phone_request():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    understanding = fallback_understanding(
        message="我想买一台华为手机，预算6000以内，主要拍照和续航",
        conversation=ConversationState(session_id="session-1"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "我想买一台华为手机，预算6000以内，主要拍照和续航"
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["category"] == "数码电子"
    assert understanding.preference_updates["brand"] == "华为"
    assert understanding.preference_updates["budget"] == 6000
    assert understanding.preference_updates["focus"] == ["拍照", "续航"]


def test_fallback_understanding_preserves_mixed_purchase_request_with_negative_brand():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    message = "想买华为手机，预算6000以内，不要苹果"

    understanding = fallback_understanding(
        message=message,
        conversation=ConversationState(session_id="session-negative-mixed"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == message
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["category"] == "数码电子"
    assert understanding.preference_updates["budget"] == 6000
    assert understanding.preference_updates["brand"] == "华为"
    assert understanding.negative_updates == {"excluded_brands": ["苹果"]}
    assert "excluded_brands" not in understanding.preference_updates

    spaced_negative_message = "想买手机，预算6000以内，不要 苹果"

    spaced_understanding = fallback_understanding(
        message=spaced_negative_message,
        conversation=ConversationState(session_id="session-negative-mixed-spaced"),
        reason="test",
    )

    assert spaced_understanding is not None
    assert spaced_understanding.intent == UserIntent.RECOMMEND
    assert spaced_understanding.purchase_need == spaced_negative_message
    assert spaced_understanding.preference_updates["target_category"] == "手机"
    assert spaced_understanding.preference_updates["category"] == "数码电子"
    assert spaced_understanding.preference_updates["budget"] == 6000
    assert spaced_understanding.negative_updates == {"excluded_brands": ["苹果"]}
    assert "brand" not in spaced_understanding.preference_updates
    assert "excluded_brands" not in spaced_understanding.preference_updates


def test_fallback_understanding_suppresses_brand_before_negative_brand_hint():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    understanding = fallback_understanding(
        message="想买手机，预算6000以内，苹果也可以不要",
        conversation=ConversationState(session_id="session-negative-brand-before"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.negative_updates == {"excluded_brands": ["苹果"]}
    assert "brand" not in understanding.preference_updates
    assert "excluded_brands" not in understanding.preference_updates


def test_fallback_understanding_preserves_negative_only_mixed_purchase_request():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    message = "推荐手机，不要苹果"

    understanding = fallback_understanding(
        message=message,
        conversation=ConversationState(session_id="session-negative-only-mixed"),
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == message
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["category"] == "数码电子"
    assert "brand" not in understanding.preference_updates
    assert understanding.negative_updates == {"excluded_brands": ["苹果"]}


def test_fallback_understanding_handles_too_expensive_with_existing_context():
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "budget": 9000,
        "focus": ["拍照"],
    }
    state.last_items = [
        ProductCard(
            product_id="p_phone_1",
            title="上一轮拍照手机",
            brand="TestBrand",
            price=8999,
            reason="适合拍照",
            evidence="命中关键词：拍照",
        )
    ]

    understanding = fallback_understanding(
        message="太贵了",
        conversation=state,
        reason="parse_validation_failure",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.UPDATE_PREFERENCE
    assert understanding.purchase_need == "预算9000以内，想买拍照好的手机"
    assert understanding.preference_updates["price_direction"] == "lower"
    assert understanding.preference_updates["avoid_current_price_band"] is True
    assert understanding.preference_updates["target_category"] == "手机"
    assert understanding.preference_updates["category"] == "数码电子"


@pytest.mark.parametrize("context_source", ["purchase_need", "target_category", "last_items"])
def test_fallback_understanding_accepts_each_active_context_source(context_source):
    from agent.fallback_understanding import fallback_understanding
    from agent.understanding import UserIntent

    state = ConversationState(session_id="session-1")
    if context_source == "purchase_need":
        state.purchase_need = "预算9000以内，想买拍照好的手机"
    elif context_source == "target_category":
        state.preferences = {"target_category": "手机"}
    else:
        state.last_items = [
            ProductCard(
                product_id="p_phone_1",
                title="上一轮拍照手机",
                brand="TestBrand",
                price=8999,
                reason="适合拍照",
                evidence="命中关键词：拍照",
            )
        ]

    understanding = fallback_understanding(
        message="太贵了",
        conversation=state,
        reason="parse_validation_failure",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.UPDATE_PREFERENCE
    assert understanding.preference_updates["price_direction"] == "lower"


def test_fallback_understanding_does_not_invent_context_for_too_expensive():
    from agent.fallback_understanding import fallback_understanding

    understanding = fallback_understanding(
        message="太贵了",
        conversation=ConversationState(session_id="session-1"),
        reason="parse_validation_failure",
    )

    assert understanding is None


def test_clarify_for_context_uses_generic_question_without_purchase_context():
    from agent.understanding import clarify_for_context

    understanding = clarify_for_context(ConversationState(session_id="session-1"))

    assert understanding.clarifying_question == "可以告诉我想买的品类、预算和最在意的点吗？"


def test_clarify_for_context_mentions_active_target_category():
    from agent.understanding import clarify_for_context

    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}

    understanding = clarify_for_context(state)

    assert "之前的手机需求" in understanding.clarifying_question
    assert "降低预算" in understanding.clarifying_question


@pytest.mark.parametrize(
    "message",
    [
        "贵一点也行",
        "贵的也可以",
        "不怕贵",
        "不贵了",
        "价格高点没关系",
    ],
)
def test_fallback_understanding_does_not_treat_higher_price_as_cheaper(message):
    from agent.fallback_understanding import fallback_understanding

    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}

    understanding = fallback_understanding(
        message=message,
        conversation=state,
        reason="parse_validation_failure",
    )

    assert understanding is None


@pytest.mark.parametrize(
    "message",
    [
        "预算6000以内，主要拍照和续航",
        "我想买点东西",
        "华为手机怎么样",
        "还是看手机吧",
        "拍照和续航好一点",
    ],
)
def test_fallback_understanding_keeps_ambiguous_messages_as_none(message):
    from agent.fallback_understanding import fallback_understanding

    understanding = fallback_understanding(
        message=message,
        conversation=ConversationState(session_id="session-1"),
        reason="test",
    )

    assert understanding is None


def test_conversation_store_creates_and_updates_state():
    store = InMemoryConversationStore()

    state = store.get_or_create("session-1")
    state.preferences["category"] = "数码电子"
    store.save(state)

    loaded = store.get_or_create("session-1")

    assert loaded.session_id == "session-1"
    assert loaded.preferences["category"] == "数码电子"


def test_conversation_state_tracks_shopping_memory_defaults():
    state = ConversationState(session_id="session-1")

    assert state.purchase_need is None
    assert state.excluded_brands == []
    assert state.target_item_index is None
    assert state.last_result_status is None
    assert state.last_no_results_need is None
    assert state.last_no_results_relax_options == []
    assert state.previous_purchase_contexts == []
    assert state.pending_restore_category is None


def test_conversation_state_tracks_negative_feedback_defaults():
    from agent.memory import ConversationState

    state = ConversationState(session_id="session-negative-defaults")

    assert state.excluded_product_ids == []
    assert state.excluded_brands == []
    assert state.excluded_keywords == []
    assert state.excluded_price_ranges == []
    assert state.negative_feedback_items == []
    assert state.latest_attempt_status is None
    assert state.latest_attempt_error is None
    assert state.latest_no_results_relax_options == []
    assert state.last_successful_items == []
    assert state.last_successful_result_id is None
    assert state.last_successful_query is None
    assert state.last_successful_filters is None


def test_purchase_context_copies_active_conversation_fields():
    from agent.memory import PurchaseContext

    state = ConversationState(session_id="session-1")
    state.purchase_need = "华为手机，预算6000以内，拍照和续航"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "focus": ["拍照", "续航"],
    }
    state.excluded_brands = ["苹果"]
    state.last_no_results_relax_options = ["提高预算"]

    archived = PurchaseContext.from_conversation(state)
    state.preferences["focus"].append("游戏")
    state.excluded_brands.append("三星")
    state.last_no_results_relax_options.append("放宽品牌")

    assert archived.purchase_need == "华为手机，预算6000以内，拍照和续航"
    assert archived.preferences["focus"] == ["拍照", "续航"]
    assert archived.excluded_brands == ["苹果"]
    assert archived.last_no_results_relax_options == ["提高预算"]
    assert archived.target_category == "手机"
    assert archived.category == "数码电子"


def test_purchase_context_copies_negative_feedback_and_latest_success_fields():
    from agent.memory import ConversationState, PurchaseContext
    from schemas.product import ProductCard

    state = ConversationState(session_id="session-negative-archive")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.excluded_product_ids = ["p_2"]
    state.excluded_brands = ["苹果"]
    state.latest_attempt_status = "success"
    state.last_successful_result_id = "result-1"
    state.last_successful_query = "拍照手机"
    state.last_successful_items = [
        ProductCard(
            product_id="p_1",
            title="测试手机",
            brand="华为",
            price=5999,
            reason="适合拍照。",
            evidence="命中拍照。",
        )
    ]

    archived = PurchaseContext.from_conversation(state)
    state.excluded_product_ids.append("p_3")
    state.last_successful_items[0].title = "被修改"

    assert archived.excluded_product_ids == ["p_2"]
    assert archived.excluded_brands == ["苹果"]
    assert archived.latest_attempt_status == "success"
    assert archived.last_successful_result_id == "result-1"
    assert archived.last_successful_query == "拍照手机"
    assert archived.last_successful_items[0].title == "测试手机"


def test_purchase_context_apply_replaces_active_conversation_fields():
    from agent.memory import PurchaseContext

    state = ConversationState(session_id="session-1")
    state.purchase_need = "办公室咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    archived = PurchaseContext(
        purchase_need="华为手机，预算6000以内",
        preferences={"target_category": "手机", "category": "数码电子", "focus": ["拍照"]},
        excluded_brands=["苹果"],
        target_category="手机",
        category="数码电子",
    )

    archived.apply_to_conversation(state)

    assert state.purchase_need == "华为手机，预算6000以内"
    assert state.preferences == {"target_category": "手机", "category": "数码电子", "focus": ["拍照"]}
    assert state.excluded_brands == ["苹果"]
    archived.preferences["focus"].append("续航")
    assert state.preferences["focus"] == ["拍照"]


def test_context_manager_archives_active_context_with_cap_and_replace():
    from agent.context_manager import archive_active_context
    from agent.memory import PurchaseContext

    state = ConversationState(session_id="session-1")
    state.purchase_need = "华为手机，预算6000以内"
    state.preferences = {"target_category": "手机", "category": "数码电子", "focus": ["拍照"]}
    state.excluded_brands = ["苹果"]
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="旧手机需求",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        ),
        PurchaseContext(
            purchase_need="办公室咖啡",
            preferences={"target_category": "咖啡", "category": "食品生活"},
            target_category="咖啡",
            category="食品生活",
        ),
        PurchaseContext(
            purchase_need="降噪耳机",
            preferences={"target_category": "耳机", "category": "数码电子"},
            target_category="耳机",
            category="数码电子",
        ),
        PurchaseContext(
            purchase_need="防晒霜",
            preferences={"target_category": "防晒", "category": "美妆护肤"},
            target_category="防晒",
            category="美妆护肤",
        ),
    ]

    archive_active_context(state, max_contexts=3)

    assert [item.target_category for item in state.previous_purchase_contexts] == ["手机", "咖啡", "耳机"]
    assert state.previous_purchase_contexts[0].purchase_need == "华为手机，预算6000以内"
    assert state.previous_purchase_contexts[0].excluded_brands == ["苹果"]
    assert [item.purchase_need for item in state.previous_purchase_contexts].count("旧手机需求") == 0


def test_context_manager_reset_for_new_target_archives_and_clears_active_context():
    from agent.context_manager import reset_for_new_target
    from schemas.chat import ChatMessage

    state = ConversationState(session_id="session-1")
    state.messages = [ChatMessage(role="user", content="想买手机")]
    state.purchase_need = "华为手机，预算6000以内"
    state.preferences = {"target_category": "手机", "category": "数码电子", "focus": ["拍照"]}
    state.excluded_brands = ["苹果"]
    state.target_item_index = 2
    state.last_query = "华为手机 拍照"
    state.last_items = [
        ProductCard(
            product_id="p_saved_1",
            title="测试手机",
            brand="TestBrand",
            price=4999,
            reason="适合拍照",
            evidence="命中关键词：拍照",
        )
    ]
    state.last_result_status = "ok"
    state.last_no_results_need = "旧无结果需求"
    state.last_no_results_relax_options = ["提高预算"]
    state.pending_restore_category = "咖啡"

    reset_for_new_target(state)

    assert state.previous_purchase_contexts[0].purchase_need == "华为手机，预算6000以内"
    assert state.purchase_need is None
    assert state.preferences == {}
    assert state.excluded_brands == []
    assert state.target_item_index is None
    assert state.last_query is None
    assert state.last_items == []
    assert state.last_result_status is None
    assert state.last_no_results_need is None
    assert state.last_no_results_relax_options == []
    assert state.messages == [ChatMessage(role="user", content="想买手机")]
    assert state.pending_restore_category == "咖啡"


def test_context_manager_request_restore_requires_existing_archive():
    from agent.context_manager import request_restore
    from agent.memory import PurchaseContext

    state = ConversationState(session_id="session-1")

    assert request_restore(state, "手机") is False
    assert state.pending_restore_category is None

    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]

    assert request_restore(state, "手机") is True
    assert state.pending_restore_category == "手机"


def test_context_manager_resolve_pending_restore_rejects_before_confirmation_without_mutation():
    from agent.context_manager import ConversationCommand, resolve_pending_restore
    from agent.understanding import UserIntent

    state = ConversationState(session_id="session-1")
    state.pending_restore_category = "手机"

    resolution = resolve_pending_restore(state, "不是，预算3000以内就行")

    assert resolution.handled is True
    assert resolution.command == ConversationCommand.REJECT_RESTORE
    assert resolution.understanding is not None
    assert resolution.understanding.intent == UserIntent.RECOMMEND
    assert resolution.understanding.reset_context is True
    assert state.pending_restore_category == "手机"


def test_context_manager_resolve_pending_restore_confirms_without_mutation():
    from agent.context_manager import ConversationCommand, resolve_pending_restore

    state = ConversationState(session_id="session-1")
    state.pending_restore_category = "手机"
    state.purchase_need = "办公室咖啡"

    resolution = resolve_pending_restore(state, "对，就按之前的")

    assert resolution.handled is True
    assert resolution.command == ConversationCommand.CONFIRM_RESTORE
    assert resolution.understanding is None
    assert state.pending_restore_category == "手机"
    assert state.purchase_need == "办公室咖啡"


def test_context_manager_resolve_pending_restore_accepts_short_confirmation():
    from agent.context_manager import ConversationCommand, resolve_pending_restore

    state = ConversationState(session_id="session-1")
    state.pending_restore_category = "手机"
    state.purchase_need = "办公室咖啡"

    resolution = resolve_pending_restore(state, "对")

    assert resolution.handled is True
    assert resolution.command == ConversationCommand.CONFIRM_RESTORE
    assert resolution.understanding is None
    assert state.pending_restore_category == "手机"
    assert state.purchase_need == "办公室咖啡"


def test_context_manager_confirm_and_reject_restore_apply_state_changes():
    from agent.context_manager import confirm_restore, reject_restore
    from agent.memory import PurchaseContext
    from agent.understanding import UserIntent

    state = ConversationState(session_id="session-1")
    state.purchase_need = "办公室咖啡，预算200以内"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.pending_restore_category = "手机"
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]

    understanding = confirm_restore(state)

    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "华为手机，预算6000以内"
    assert understanding.preference_updates == {"target_category": "手机", "category": "数码电子"}
    assert state.purchase_need == "华为手机，预算6000以内"
    assert state.preferences == {"target_category": "手机", "category": "数码电子"}
    assert state.pending_restore_category is None
    assert any(item.target_category == "咖啡" for item in state.previous_purchase_contexts)

    state.pending_restore_category = "手机"
    reject_restore(state)

    assert state.pending_restore_category is None
    assert state.purchase_need == "华为手机，预算6000以内"


def test_context_manager_resolve_pending_restore_complete_new_request_clears_later():
    from agent.context_manager import resolve_pending_restore

    state = ConversationState(session_id="session-1")
    state.pending_restore_category = "手机"

    resolution = resolve_pending_restore(state, "我想买咖啡，预算200以内，低糖")

    assert resolution.handled is False
    assert resolution.clear_pending_before_understanding is True
    assert resolution.understanding is None
    assert state.pending_restore_category == "手机"


def test_llm_understanding_service_parses_valid_json():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    llm = FakeLLM(
        json.dumps(
            {
                "intent": "recommend",
                "confidence": 0.91,
                "purchase_need": "9000以内、拍照好的手机",
                "preference_updates": {
                    "category": "手机",
                    "budget": "9000以内",
                    "focus": ["拍照"],
                },
                "target_item_index": None,
                "clarifying_question": None,
            },
            ensure_ascii=False,
        )
    )
    service = LLMUserUnderstandingService(llm=llm)
    state = ConversationState(session_id="session-1")

    understanding = service.understand(message="预算9000以内的拍照手机", conversation=state)

    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.confidence == 0.91
    assert understanding.purchase_need == "9000以内、拍照好的手机"
    assert understanding.preference_updates["focus"] == ["拍照"]
    assert llm.calls[0]["max_tokens"] >= 500


def test_llm_understanding_prompt_mentions_context_transition_fields():
    from agent.memory import PurchaseContext
    from agent.understanding import LLMUserUnderstandingService

    service = LLMUserUnderstandingService(llm=FakeLLM("{}"))
    state = ConversationState(session_id="session-1")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.pending_restore_category = "手机"
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]

    messages = service._build_messages("还是看手机吧", state)
    system_prompt = messages[0]["content"]
    context_block = messages[1]["content"]

    assert "reset_context" in system_prompt
    assert "restore_context_category" in system_prompt
    assert "target_category" in system_prompt
    assert "category means catalog category" in system_prompt
    assert "pending_restore_category" in context_block
    assert "previous_purchase_contexts" in context_block
    assert "手机" in context_block


def test_llm_understanding_prompt_mentions_short_price_feedback_schema_rules():
    from agent.understanding import LLMUserUnderstandingService

    service = LLMUserUnderstandingService(llm=FakeLLM("{}"))

    prompt = service._system_prompt()

    assert "太贵了" in prompt
    assert "intent=update_preference" in prompt
    assert "preference_updates must be a JSON object" in prompt
    assert "target_item_index must be null" in prompt


def test_llm_understanding_service_normalizes_missing_default_fields():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    llm = FakeLLM(
        json.dumps(
            {
                "intent": "recommend",
                "purchase_need": "想买一台华为手机，预算6000以内，主要拍照和续航",
            },
            ensure_ascii=False,
        )
    )
    service = LLMUserUnderstandingService(llm=llm)

    understanding = service.understand(
        message="想买一台华为手机，预算6000以内，主要拍照和续航",
        conversation=ConversationState(session_id="session-1"),
    )

    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.confidence == 0.5
    assert understanding.preference_updates == {}
    assert understanding.target_item_index is None
    assert understanding.clarifying_question is None
    assert understanding.reset_context is False
    assert understanding.restore_context_category is None


def test_normalize_understanding_payload_sanitizes_invalid_target_item_index():
    from agent.understanding import normalize_understanding_payload

    normalized = normalize_understanding_payload(
        {
            "intent": "update_preference",
            "confidence": 0.8,
            "purchase_need": None,
            "preference_updates": {},
            "target_item_index": 0,
            "clarifying_question": None,
        }
    )

    assert normalized["target_item_index"] is None


def test_normalize_understanding_payload_sanitizes_bool_target_item_index():
    from agent.understanding import normalize_understanding_payload

    normalized = normalize_understanding_payload(
        {
            "intent": "update_preference",
            "confidence": 0.8,
            "purchase_need": None,
            "preference_updates": {},
            "target_item_index": True,
            "clarifying_question": None,
        }
    )

    assert normalized["target_item_index"] is None


def test_normalize_understanding_payload_sanitizes_non_dict_preference_updates():
    from agent.understanding import normalize_understanding_payload

    normalized = normalize_understanding_payload(
        {
            "intent": "update_preference",
            "confidence": 0.8,
            "purchase_need": None,
            "preference_updates": ["优先便宜一些"],
            "target_item_index": None,
            "clarifying_question": None,
        }
    )

    assert normalized["preference_updates"] == {}


def test_normalize_understanding_payload_sanitizes_non_dict_negative_updates():
    from agent.understanding import normalize_understanding_payload

    normalized = normalize_understanding_payload(
        {
            "intent": "update_preference",
            "confidence": 0.8,
            "negative_updates": ["不要苹果"],
        }
    )

    assert normalized["negative_updates"] == {}


def test_user_understanding_accepts_negative_updates():
    from agent.understanding import UserIntent, UserUnderstanding

    understanding = UserUnderstanding(
        intent=UserIntent.UPDATE_PREFERENCE,
        confidence=0.9,
        negative_updates={"excluded_brands": ["苹果"]},
    )

    assert understanding.negative_updates == {"excluded_brands": ["苹果"]}


def test_fallback_understanding_puts_negative_brand_in_negative_updates_only():
    from agent.fallback_understanding import fallback_understanding
    from agent.memory import ConversationState
    from agent.understanding import UserIntent

    state = ConversationState(session_id="session-negative-fallback")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}

    understanding = fallback_understanding(
        message="不要苹果",
        conversation=state,
        reason="test",
    )

    assert understanding is not None
    assert understanding.intent == UserIntent.UPDATE_PREFERENCE
    assert understanding.negative_updates == {"excluded_brands": ["苹果"]}
    assert "brand" not in understanding.preference_updates
    assert "excluded_brands" not in understanding.preference_updates


def test_normalize_understanding_payload_uses_fresh_default_preference_updates():
    from agent.understanding import normalize_understanding_payload

    first = normalize_understanding_payload(
        {
            "intent": "recommend",
            "confidence": 0.8,
            "purchase_need": "想买手机",
            "target_item_index": None,
            "clarifying_question": None,
        }
    )
    second = normalize_understanding_payload(
        {
            "intent": "recommend",
            "confidence": 0.8,
            "purchase_need": "想买咖啡",
            "target_item_index": None,
            "clarifying_question": None,
        }
    )

    first["preference_updates"]["target_category"] = "手机"

    assert second["preference_updates"] == {}


def test_llm_understanding_service_rejects_top_level_json_list():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(llm=FakeLLM('[{"intent": "recommend"}]'))

    understanding = service.understand(
        message="你好",
        conversation=ConversationState(session_id="session-1"),
    )

    assert understanding.intent == UserIntent.CLARIFY


def test_llm_understanding_service_returns_clarify_on_invalid_json():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(llm=FakeLLM("不是 JSON"))

    understanding = service.understand(
        message="这个太贵了",
        conversation=ConversationState(session_id="session-1"),
    )

    assert understanding.intent == UserIntent.CLARIFY
    assert understanding.confidence == 0.0
    assert understanding.clarifying_question


def test_llm_understanding_service_uses_contextual_clarify_after_parse_failure():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(llm=FakeLLM("不是 JSON"))
    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}

    understanding = service.understand(message="这个不太行", conversation=state)

    assert understanding.intent == UserIntent.CLARIFY
    assert "之前的手机需求" in understanding.clarifying_question
    assert "可以告诉我想买的品类" not in understanding.clarifying_question


def test_llm_understanding_service_fallbacks_on_invalid_json_complete_request():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(llm=FakeLLM("不是 JSON"))

    understanding = service.understand(
        message="我想买一台华为手机，预算6000以内，主要拍照和续航",
        conversation=ConversationState(session_id="session-1"),
    )

    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.preference_updates["target_category"] == "手机"


def test_llm_understanding_service_contextual_fallback_after_dirty_update_schema():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(
        llm=FakeLLM(
            json.dumps(
                {
                    "intent": "update_preference",
                    "confidence": 0.8,
                    "purchase_need": None,
                    "preference_updates": ["优先便宜一些"],
                    "target_item_index": 0,
                    "clarifying_question": None,
                },
                ensure_ascii=False,
            )
        )
    )
    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}

    understanding = service.understand(message="太贵了", conversation=state)

    assert understanding.intent == UserIntent.UPDATE_PREFERENCE
    assert understanding.preference_updates["price_direction"] == "lower"
    assert understanding.preference_updates["avoid_current_price_band"] is True
    assert understanding.target_item_index is None


def test_llm_understanding_service_contextual_fallback_when_llm_clarifies_existing_context():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(
        llm=FakeLLM(
            json.dumps(
                {
                    "intent": "clarify",
                    "confidence": 0.8,
                    "purchase_need": None,
                    "preference_updates": {},
                    "target_item_index": None,
                    "clarifying_question": "你想买什么？",
                },
                ensure_ascii=False,
            )
        )
    )
    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}

    understanding = service.understand(message="太贵了", conversation=state)

    assert understanding.intent == UserIntent.UPDATE_PREFERENCE
    assert understanding.preference_updates["price_direction"] == "lower"


def test_llm_understanding_service_preserves_llm_clarify_when_contextual_fallback_misses():
    from agent.memory import PurchaseContext
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(
        llm=FakeLLM(
            json.dumps(
                {
                    "intent": "clarify",
                    "confidence": 0.8,
                    "purchase_need": None,
                    "preference_updates": {},
                    "target_item_index": None,
                    "clarifying_question": "是否恢复之前的手机需求？",
                    "restore_context_category": "手机",
                },
                ensure_ascii=False,
            )
        )
    )
    state = ConversationState(session_id="session-1")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="预算9000以内，想买拍照好的手机",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]

    understanding = service.understand(message="还是看手机吧", conversation=state)

    assert understanding.intent == UserIntent.CLARIFY
    assert understanding.confidence == 0.8
    assert understanding.clarifying_question == "是否恢复之前的手机需求？"
    assert understanding.restore_context_category == "手机"


def test_llm_understanding_service_overrides_clarify_for_complete_request():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(
        llm=FakeLLM(
            json.dumps(
                {
                    "intent": "clarify",
                    "confidence": 0.8,
                    "clarifying_question": "你想买什么？",
                },
                ensure_ascii=False,
            )
        )
    )

    understanding = service.understand(
        message="我想买一台华为手机，预算6000以内，主要拍照和续航",
        conversation=ConversationState(session_id="session-1"),
    )

    assert understanding.intent == UserIntent.RECOMMEND


def test_llm_understanding_service_fallbacks_when_purchase_need_missing_without_active_need():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(
        llm=FakeLLM(
            json.dumps(
                {
                    "intent": "recommend",
                    "confidence": 0.8,
                    "preference_updates": {"target_category": "手机"},
                },
                ensure_ascii=False,
            )
        )
    )

    understanding = service.understand(
        message="我想买一台华为手机，预算6000以内，主要拍照和续航",
        conversation=ConversationState(session_id="session-1"),
    )

    assert understanding.intent == UserIntent.RECOMMEND
    assert understanding.purchase_need == "我想买一台华为手机，预算6000以内，主要拍照和续航"


def test_llm_understanding_service_clarifies_when_purchase_need_missing_and_fallback_unsafe():
    from agent.understanding import LLMUserUnderstandingService, UserIntent

    service = LLMUserUnderstandingService(
        llm=FakeLLM(
            json.dumps(
                {
                    "intent": "recommend",
                    "confidence": 0.8,
                    "preference_updates": {"focus": ["拍照"]},
                },
                ensure_ascii=False,
            )
        )
    )

    understanding = service.understand(
        message="拍照和续航好一点",
        conversation=ConversationState(session_id="session-1"),
    )

    assert understanding.intent == UserIntent.CLARIFY


def test_recommendation_tool_wraps_recommendation_pipeline():
    tool = RecommendationTool()

    result = tool.run("预算9000以内的拍照手机", top_k=2)

    assert result.query == "预算9000以内的拍照手机"
    assert len(result.items) == 2
    assert result.filters.category == "数码电子"


def test_build_recommendation_query_adds_structured_target_and_budget():
    from agent.query_builder import build_recommendation_query

    state = ConversationState(session_id="session-1")
    state.purchase_need = "不是，预算3000以内就行"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "budget": 3000,
        "focus": ["拍照"],
    }

    query = build_recommendation_query(state)

    assert query.startswith("不是，预算3000以内就行")
    assert "手机" in query
    assert "预算3000以内" in query
    assert "拍照" in query
    assert query.count("预算3000以内") == 1


def test_build_recommendation_query_merges_excluded_brands_and_price_preference():
    from agent.query_builder import build_recommendation_query

    state = ConversationState(session_id="session-1")
    state.purchase_need = "拍照好的手机"
    state.preferences = {
        "excluded_brands": ["苹果"],
        "price_preference": "lower",
    }
    state.excluded_brands = ["三星"]

    query = build_recommendation_query(state)

    assert ("不要三星、苹果" in query) or ("不要苹果、三星" in query)
    assert "价格更低" in query


def test_build_recommendation_query_consumes_lower_price_direction():
    from agent.query_builder import build_recommendation_query

    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "budget": 9000,
        "focus": ["拍照"],
        "price_direction": "lower",
        "avoid_current_price_band": True,
    }

    query = build_recommendation_query(state)

    assert "价格更低" in query
    assert "性价比优先" in query
    assert "避免上一轮同价位" in query


def test_build_recommendation_query_includes_max_price_upper_limit():
    from agent.query_builder import build_recommendation_query

    state = ConversationState(session_id="session-1")
    state.purchase_need = "拍照好的手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "max_price": 5000,
    }

    query = build_recommendation_query(state)

    assert "预算5000以内" in query


def test_build_recommendation_query_prefers_stricter_numeric_price_limit():
    from agent.query_builder import build_recommendation_query

    state = ConversationState(session_id="session-1")
    state.purchase_need = "拍照好的手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "budget": 9000,
        "max_price": 5000,
    }

    query = build_recommendation_query(state)

    assert "预算5000以内" in query
    assert "预算9000以内" not in query


def test_build_recommendation_query_places_stricter_structured_price_before_old_purchase_need_budget():
    from agent.query_builder import build_recommendation_query

    state = ConversationState(session_id="session-1")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "max_price": 5000,
    }

    query = build_recommendation_query(state)

    assert "预算5000以内" in query
    assert "预算9000以内" in query
    assert query.index("预算5000以内") < query.index("预算9000以内")
    assert "拍照好的手机" in query


def test_load_app_config_reads_agent_runner(monkeypatch):
    monkeypatch.setenv("AGENT_RUNNER", "langgraph")

    config = load_app_config(env_file=None)

    assert config.agent_runner == "langgraph"


def test_load_app_config_defaults_to_langgraph_when_runner_is_unset(monkeypatch):
    monkeypatch.delenv("AGENT_RUNNER", raising=False)

    config = load_app_config(env_file=None)

    assert config.agent_runner == "langgraph"


def test_create_agent_runner_rejects_removed_simple_runner():
    from agent.runner import create_agent_runner

    with pytest.raises(ValueError, match="AGENT_RUNNER"):
        create_agent_runner(config=AppConfig(agent_runner="simple"))


def test_create_agent_runner_defaults_to_langgraph_runner():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.runner import create_agent_runner

    runner = create_agent_runner(config=AppConfig())

    assert isinstance(runner, LangGraphAgentRunner)


def test_create_agent_runner_can_create_langgraph_runner():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.runner import create_agent_runner

    runner = create_agent_runner(config=AppConfig(agent_runner="langgraph"))

    assert isinstance(runner, LangGraphAgentRunner)


def test_create_agent_runner_passes_config_llm_to_langgraph_runner():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.runner import create_agent_runner

    llm_config = LLMConfig(enabled=True, api_key="test-key", model="test-model")
    config = AppConfig(llm=llm_config)

    runner = create_agent_runner(config=config)

    assert isinstance(runner, LangGraphAgentRunner)
    assert runner.llm_config is llm_config


def test_create_agent_runner_accepts_understanding_service():
    from agent.runner import create_agent_runner
    from agent.understanding import UserIntent

    service = FakeUnderstandingService(
        [
            make_understanding(
                intent=UserIntent.RECOMMEND,
                purchase_need="9000以内、拍照好的手机",
                preference_updates={"category": "手机"},
            )
        ]
    )

    runner = create_agent_runner(
        config=AppConfig(agent_runner="langgraph"),
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=service,
    )

    response = runner.run("session-1", "预算9000以内的拍照手机")

    assert response.state["intent"] == "recommend"
    assert service.calls[0]["message"] == "预算9000以内的拍照手机"


def test_create_agent_runner_rejects_unknown_runner():
    from agent.runner import create_agent_runner

    with pytest.raises(ValueError, match="AGENT_RUNNER"):
        create_agent_runner(config=AppConfig(agent_runner="unknown"))


def test_langgraph_agent_runner_recommends_and_keeps_state():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="9000以内、拍照好的手机",
                    preference_updates={
                        "category": "数码电子",
                        "budget": "9000以内",
                        "focus": ["拍照"],
                    },
                )
            ]
        ),
    )

    response = runner.run("langgraph-session-1", "预算9000以内的拍照手机")

    assert response.session_id == "langgraph-session-1"
    assert len(response.items) == 3
    assert response.state["intent"] == "recommend"
    assert response.state["action"] == "recommend"
    assert response.state["confidence"] == 0.9
    assert response.state["purchase_need"] == "9000以内、拍照好的手机"
    assert response.state["preferences"]["category"] == "数码电子"
    assert response.state["preferences"]["focus"] == ["拍照"]


def test_langgraph_agent_runner_uses_previous_state_for_follow_up():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="9000以内、拍照好的手机",
                    preference_updates={
                        "category": "数码电子",
                        "budget": "9000以内",
                        "focus": ["拍照"],
                    },
                ),
                make_understanding(
                    intent=UserIntent.UPDATE_PREFERENCE,
                    purchase_need="价格更低、拍照好的手机",
                    preference_updates={
                        "price_preference": "lower",
                        "focus": ["拍照"],
                    },
                ),
            ]
        ),
    )

    runner.run("langgraph-session-1", "预算9000以内的拍照手机")
    response = runner.run("langgraph-session-1", "再便宜一点")

    assert response.state["intent"] == "update_preference"
    assert response.state["action"] == "recommend"
    assert response.state["preferences"]["price_preference"] == "lower"
    assert response.items
    assert response.state["preferences"]["category"] == "数码电子"
    assert response.state["purchase_need"] == "价格更低、拍照好的手机"

def test_runner_recommends_after_contextual_price_feedback_from_dirty_llm_schema():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import LLMUserUnderstandingService

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-contextual-price")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "budget": 9000,
        "focus": ["拍照"],
    }
    state.last_items = [
        ProductCard(
            product_id="p_saved_phone",
            title="上一轮拍照手机",
            brand="SavedBrand",
            price=8999,
            reason="适合拍照",
            evidence="命中关键词：拍照",
        )
    ]
    store.save(state)
    captured_queries: list[str] = []

    def capture_recommendation(query: str, top_k: int = 3):
        captured_queries.append(query)
        return single_recommendation(query, top_k=top_k)

    understanding_service = LLMUserUnderstandingService(
        llm=FakeLLM(
            json.dumps(
                {
                    "intent": "update_preference",
                    "confidence": 0.8,
                    "purchase_need": None,
                    "preference_updates": ["优先便宜一些"],
                    "target_item_index": 0,
                    "clarifying_question": None,
                },
                ensure_ascii=False,
            )
        )
    )
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=capture_recommendation),
        understanding_service=understanding_service,
    )

    response = runner.run("langgraph-session-contextual-price", "太贵了")
    saved = store.get_or_create("langgraph-session-contextual-price")

    assert response.state["intent"] == "update_preference"
    assert response.state["action"] == "recommend"
    assert response.state["preferences"]["price_direction"] == "lower"
    assert response.state["preferences"]["avoid_current_price_band"] is True
    assert saved.preferences["price_direction"] == "lower"
    assert captured_queries
    assert "价格更低" in captured_queries[0]
    assert "性价比优先" in captured_queries[0]
    assert "可以告诉我想买的品类" not in response.reply


def test_langgraph_runner_uses_deterministic_query_builder():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    captured_queries: list[str] = []

    def capture_recommendation(query: str, top_k: int = 3):
        captured_queries.append(query)
        return single_recommendation(query, top_k=top_k)

    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(recommend_func=capture_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="不是，预算3000以内就行",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "budget": 3000,
                    },
                )
            ]
        ),
    )

    runner.run("langgraph-session-query-builder", "不是，预算3000以内就行")

    assert captured_queries
    assert "手机" in captured_queries[0]
    assert "预算3000以内" in captured_queries[0]


def test_langgraph_runner_requests_restore_instead_of_overwriting_active_context():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.memory import PurchaseContext
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-restore-request")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]
    store.save(state)

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.CLARIFY,
                    clarifying_question="要恢复之前的手机需求吗？",
                    restore_context_category="手机",
                )
            ]
        ),
    )

    response = runner.run("langgraph-session-restore-request", "还是看手机吧")
    saved = store.get_or_create("langgraph-session-restore-request")

    assert response.state["intent"] == "clarify"
    assert response.state["action"] == "clarify"
    assert "恢复之前的手机需求" in response.reply
    assert saved.purchase_need == "办公室喝的咖啡"
    assert saved.preferences["target_category"] == "咖啡"
    assert saved.pending_restore_category == "手机"


def test_langgraph_runner_applies_reset_context_before_new_purchase_need():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent
    from schemas.recommend import RecommendFilters

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-reset-context")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.last_query = "办公室喝的咖啡"
    state.last_filters = RecommendFilters(category="食品生活", max_price=200)
    state.last_items = [
        ProductCard(
            product_id="p_coffee_1",
            title="旧咖啡",
            brand="CoffeeBrand",
            price=99,
            reason="旧推荐",
            evidence="旧证据",
        )
    ]
    store.save(state)

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=empty_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="华为手机，预算6000以内",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                    },
                    reset_context=True,
                )
            ]
        ),
    )

    response = runner.run("langgraph-session-reset-context", "华为手机，预算6000以内")
    saved = store.get_or_create("langgraph-session-reset-context")

    assert response.state["intent"] == "recommend"
    assert saved.purchase_need == "华为手机，预算6000以内"
    assert saved.preferences["target_category"] == "手机"
    assert saved.previous_purchase_contexts[0].purchase_need == "办公室喝的咖啡"
    assert saved.previous_purchase_contexts[0].target_category == "咖啡"
    assert saved.last_items == []
    assert saved.last_filters is not None
    assert saved.last_filters.category == "数码电子"


def test_langgraph_runner_resolves_pending_restore_confirmation_in_update_memory():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.memory import PurchaseContext

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-restore-confirm")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.pending_restore_category = "手机"
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]
    store.save(state)

    service = FakeUnderstandingService([])
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=single_recommendation),
        understanding_service=service,
    )

    response = runner.run("langgraph-session-restore-confirm", "对，就按之前的")
    saved = store.get_or_create("langgraph-session-restore-confirm")

    assert service.calls == []
    assert response.state["intent"] == "recommend"
    assert response.state["action"] == "recommend"
    assert response.items
    assert saved.purchase_need == "华为手机，预算6000以内"
    assert saved.preferences["target_category"] == "手机"
    assert saved.pending_restore_category is None
    assert any(item.target_category == "咖啡" for item in saved.previous_purchase_contexts)


def test_langgraph_runner_rejects_pending_restore_and_uses_new_constraints():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.memory import PurchaseContext

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-restore-reject")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.pending_restore_category = "手机"
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]
    store.save(state)

    captured_queries: list[str] = []

    def capture_recommendation(query: str, top_k: int = 3):
        captured_queries.append(query)
        return single_recommendation(query, top_k=top_k)

    service = FakeUnderstandingService([])
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=capture_recommendation),
        understanding_service=service,
    )

    response = runner.run("langgraph-session-restore-reject", "不是，预算3000以内就行")
    saved = store.get_or_create("langgraph-session-restore-reject")

    assert service.calls == []
    assert saved.pending_restore_category is None
    assert saved.purchase_need == "不是，预算3000以内就行"
    assert saved.preferences["target_category"] == "手机"
    assert saved.preferences["budget"] == 3000
    assert any(item.target_category == "咖啡" for item in saved.previous_purchase_contexts)
    assert captured_queries
    assert "手机" in captured_queries[0]
    assert "预算3000以内" in captured_queries[0]
    assert "食品生活" not in captured_queries[0]
    assert response.state["intent"] == "recommend"
    assert response.state["action"] == "recommend"


def test_langgraph_runner_pending_restore_complete_new_request_calls_understanding_after_clear():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.memory import PurchaseContext
    from agent.understanding import UserIntent

    class SnapshotUnderstandingService:
        def __init__(self):
            self.calls = []

        def understand(self, *, message, conversation):
            self.calls.append(
                {
                    "message": message,
                    "pending_restore_category": conversation.pending_restore_category,
                }
            )
            return make_understanding(
                intent=UserIntent.RECOMMEND,
                purchase_need="办公室咖啡，预算200以内，低糖",
                preference_updates={
                    "target_category": "咖啡",
                    "category": "食品生活",
                    "budget": 200,
                    "focus": ["低糖"],
                },
                reset_context=True,
            )

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-restore-new-request")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.pending_restore_category = "手机"
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={"target_category": "手机", "category": "数码电子"},
            target_category="手机",
            category="数码电子",
        )
    ]
    store.save(state)

    captured_queries: list[str] = []

    def coffee_recommendation(query: str, top_k: int = 3):
        captured_queries.append(query)
        return {
            "query": query,
            "filters": {
                "category": "食品生活",
                "max_price": 200,
                "brand": None,
                "keywords": ["咖啡", "低糖"],
            },
            "items": [
                {
                    "product_id": "p_coffee_test",
                    "title": "测试低糖咖啡",
                    "brand": "CoffeeBrand",
                    "price": 99,
                    "reason": "适合低糖偏好。",
                    "evidence": "命中关键词：低糖",
                }
            ][:top_k],
        }

    service = SnapshotUnderstandingService()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=coffee_recommendation),
        understanding_service=service,
    )

    response = runner.run("langgraph-session-restore-new-request", "我想买咖啡，预算200以内，低糖")
    saved = store.get_or_create("langgraph-session-restore-new-request")

    assert service.calls == [
        {
            "message": "我想买咖啡，预算200以内，低糖",
            "pending_restore_category": None,
        }
    ]
    assert saved.pending_restore_category is None
    assert saved.purchase_need == "办公室咖啡，预算200以内，低糖"
    assert saved.preferences["target_category"] == "咖啡"
    assert saved.preferences["budget"] == 200
    assert any(item.target_category == "咖啡" for item in saved.previous_purchase_contexts)
    assert captured_queries
    assert "咖啡" in captured_queries[0]
    assert "预算200以内" in captured_queries[0]
    assert "低糖" in captured_queries[0]
    assert response.state["intent"] == "recommend"
    assert response.state["action"] == "recommend"


def test_langgraph_runner_full_restore_round_trip():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.memory import PurchaseContext
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-restore-round-trip")
    state.purchase_need = "办公室喝的咖啡"
    state.preferences = {"target_category": "咖啡", "category": "食品生活"}
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="华为手机，预算6000以内",
            preferences={
                "target_category": "手机",
                "category": "数码电子",
                "budget": 6000,
                "focus": ["拍照"],
            },
            target_category="手机",
            category="数码电子",
        )
    ]
    store.save(state)

    captured_queries: list[str] = []

    def capture_recommendation(query: str, top_k: int = 3):
        captured_queries.append(query)
        return single_recommendation(query, top_k=top_k)

    service = FakeUnderstandingService(
        [
            make_understanding(
                intent=UserIntent.CLARIFY,
                clarifying_question="要恢复之前的手机需求吗？",
                restore_context_category="手机",
            )
        ]
    )
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=capture_recommendation),
        understanding_service=service,
    )

    first = runner.run("langgraph-session-restore-round-trip", "还是看手机吧")
    after_first = store.get_or_create("langgraph-session-restore-round-trip")

    assert len(service.calls) == 1
    assert captured_queries == []
    assert first.state["intent"] == "clarify"
    assert first.state["action"] == "clarify"
    assert after_first.purchase_need == "办公室喝的咖啡"
    assert after_first.preferences["target_category"] == "咖啡"
    assert after_first.pending_restore_category == "手机"

    second = runner.run("langgraph-session-restore-round-trip", "对，就按之前的")
    after_second = store.get_or_create("langgraph-session-restore-round-trip")

    assert len(service.calls) == 1
    assert second.state["intent"] == "recommend"
    assert second.state["action"] == "recommend"
    assert second.items
    assert after_second.pending_restore_category is None
    assert after_second.purchase_need == "华为手机，预算6000以内"
    assert after_second.preferences["target_category"] == "手机"
    assert any(item.target_category == "咖啡" for item in after_second.previous_purchase_contexts)
    assert captured_queries
    assert "手机" in captured_queries[0]
    assert "预算6000以内" in captured_queries[0]


def test_langgraph_agent_runner_explains_indexed_recommendation():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="9000以内、拍照好的手机",
                    preference_updates={"category": "数码电子"},
                ),
                make_understanding(
                    intent=UserIntent.EXPLAIN,
                    target_item_index=2,
                ),
            ]
        ),
    )

    first = runner.run("langgraph-session-1", "预算9000以内的拍照手机")
    response = runner.run("langgraph-session-1", "第二个为什么适合我")

    assert response.state["intent"] == "explain"
    assert response.state["action"] == "explain"
    assert first.items[1].title in response.reply
    assert "因为" in response.reply
    assert response.items == first.items


def test_langgraph_agent_runner_clarifies_when_intent_missing():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    runner = LangGraphAgentRunner(
        store=InMemoryConversationStore(),
        recommendation_tool=RecommendationTool(),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.CLARIFY,
                    clarifying_question="可以告诉我品类、预算和最在意的点吗？",
                    confidence=0.5,
                )
            ]
        ),
    )

    response = runner.run("langgraph-session-1", "你好")

    assert response.state["intent"] == "clarify"
    assert response.state["action"] == "clarify"
    assert response.state["confidence"] == 0.5
    assert "预算" in response.reply
    assert response.items == []


def test_runner_uses_contextual_clarify_when_existing_purchase_need_is_present():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import LLMUserUnderstandingService

    store = InMemoryConversationStore()
    state = store.get_or_create("langgraph-session-contextual-clarify")
    state.purchase_need = "预算9000以内，想买拍照好的手机"
    state.preferences = {"target_category": "手机", "category": "数码电子"}
    store.save(state)

    def fail_recommendation(query: str, top_k: int = 3):
        raise AssertionError("上下文澄清不应调用推荐工具")

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=fail_recommendation),
        understanding_service=LLMUserUnderstandingService(llm=FakeLLM("不是 JSON")),
    )

    response = runner.run("langgraph-session-contextual-clarify", "这个不太行")

    assert response.state["intent"] == "clarify"
    assert response.state["action"] == "clarify"
    assert "之前的手机需求" in response.reply
    assert "降低预算" in response.reply
    assert "可以告诉我想买的品类" not in response.reply
    assert response.items == []


def test_langgraph_agent_runner_handles_no_results_without_overwriting_last_items():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    prior = store.get_or_create("langgraph-session-1")
    prior.last_items = [
        ProductCard(
            product_id="p_saved_1",
            title="上一轮手机",
            brand="SavedBrand",
            price=4999,
            reason="上一轮理由",
            evidence="上一轮证据",
        )
    ]
    store.save(prior)
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=empty_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="3000以内、拍照强、折叠屏手机",
                    preference_updates={
                        "category": "手机",
                        "budget": "3000以内",
                        "focus": ["拍照强", "折叠屏"],
                    },
                )
            ]
        ),
    )

    response = runner.run("langgraph-session-1", "3000以内拍照强的折叠屏手机")
    state = store.get_or_create("langgraph-session-1")

    assert response.items == []
    assert response.state["result_status"] == "no_results"
    assert "没有找到" in response.reply
    assert "3000以内、拍照强、折叠屏手机" in response.reply
    assert state.last_items[0].title == "上一轮手机"
    assert state.last_no_results_need == "3000以内、拍照强、折叠屏手机"
    assert len(state.last_no_results_relax_options) >= 2


def test_langgraph_agent_runner_returns_tool_error_without_overwriting_last_items():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    store = InMemoryConversationStore()
    prior = store.get_or_create("langgraph-session-1")
    prior.last_items = [
        ProductCard(
            product_id="p_saved_1",
            title="上一轮手机",
            brand="SavedBrand",
            price=4999,
            reason="上一轮理由",
            evidence="上一轮证据",
        )
    ]
    store.save(prior)

    def broken_recommendation(query: str, top_k: int = 3):
        raise RuntimeError("boom")

    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=broken_recommendation),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="华为手机，预算6000以内",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "budget": 6000,
                    },
                )
            ]
        ),
    )

    response = runner.run("langgraph-session-1", "华为手机，预算6000以内")
    state = store.get_or_create("langgraph-session-1")

    assert response.items == []
    assert "推荐服务暂时不可用" in response.reply
    assert response.state["result_status"] == "tool_error"
    assert response.state["tool_error"] == "recommendation_failed"
    assert state.last_result_status == "tool_error"
    assert state.last_items[0].title == "上一轮手机"
    assert "华为手机" in (state.last_query or "")
    assert state.last_no_results_need is None
    assert state.last_no_results_relax_options == []


def test_langgraph_agent_runner_explains_previous_success_after_no_results():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    recommendation_calls = []

    def recommendation_sequence(query: str, top_k: int = 3):
        recommendation_calls.append(query)
        if len(recommendation_calls) == 1:
            return single_recommendation(query, top_k=top_k)
        if len(recommendation_calls) == 2:
            return empty_recommendation(query, top_k=top_k)
        raise AssertionError("解释上一轮商品时不应再次调用推荐工具")

    store = InMemoryConversationStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=recommendation_sequence),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="9000以内、拍照好的手机",
                    preference_updates={"target_category": "手机", "category": "数码电子"},
                ),
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="3000以内、拍照强、折叠屏手机",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "budget": "3000以内",
                        "focus": ["拍照强", "折叠屏"],
                    },
                ),
                make_understanding(intent=UserIntent.EXPLAIN, target_item_index=1),
            ]
        ),
    )

    first = runner.run("langgraph-session-explain-no-results", "预算9000以内的拍照手机")
    second = runner.run("langgraph-session-explain-no-results", "3000以内拍照强的折叠屏手机")
    state_after_second = store.get_or_create("langgraph-session-explain-no-results")
    third = runner.run("langgraph-session-explain-no-results", "为什么第一款适合我")

    assert len(recommendation_calls) == 2
    assert second.state["result_status"] == "no_results"
    assert state_after_second.last_items == first.items
    assert third.state["intent"] == "explain"
    assert third.state["action"] == "explain"
    assert "result_status" not in third.state
    assert "tool_error" not in third.state
    assert first.items[0].title in third.reply
    assert first.items[0].evidence in third.reply
    assert third.items == first.items


def test_langgraph_agent_runner_explains_previous_success_after_tool_error():
    from agent.graph.runner import LangGraphAgentRunner
    from agent.understanding import UserIntent

    recommendation_calls = []

    def recommendation_sequence(query: str, top_k: int = 3):
        recommendation_calls.append(query)
        if len(recommendation_calls) == 1:
            return single_recommendation(query, top_k=top_k)
        if len(recommendation_calls) == 2:
            raise RuntimeError("boom")
        raise AssertionError("解释上一轮商品时不应再次调用推荐工具")

    store = InMemoryConversationStore()
    runner = LangGraphAgentRunner(
        store=store,
        recommendation_tool=RecommendationTool(recommend_func=recommendation_sequence),
        understanding_service=FakeUnderstandingService(
            [
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="9000以内、拍照好的手机",
                    preference_updates={"target_category": "手机", "category": "数码电子"},
                ),
                make_understanding(
                    intent=UserIntent.RECOMMEND,
                    purchase_need="华为手机，预算6000以内",
                    preference_updates={
                        "target_category": "手机",
                        "category": "数码电子",
                        "budget": 6000,
                    },
                ),
                make_understanding(intent=UserIntent.EXPLAIN, target_item_index=1),
            ]
        ),
    )

    first = runner.run("langgraph-session-explain-tool-error", "预算9000以内的拍照手机")
    second = runner.run("langgraph-session-explain-tool-error", "华为手机，预算6000以内")
    state_after_second = store.get_or_create("langgraph-session-explain-tool-error")
    third = runner.run("langgraph-session-explain-tool-error", "为什么第一款适合我")

    assert len(recommendation_calls) == 2
    assert second.state["result_status"] == "tool_error"
    assert second.state["tool_error"] == "recommendation_failed"
    assert state_after_second.last_items == first.items
    assert third.state["intent"] == "explain"
    assert third.state["action"] == "explain"
    assert "result_status" not in third.state
    assert "tool_error" not in third.state
    assert first.items[0].title in third.reply
    assert first.items[0].evidence in third.reply
    assert third.items == first.items


def test_openai_invoke_chat_client_accepts_custom_max_tokens(monkeypatch):
    from llm import client as llm_client

    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Message:
                content = "完整购买意图"

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url, timeout):
            self.chat = FakeChat()

    monkeypatch.setattr(llm_client, "OpenAI", FakeOpenAI, raising=False)

    model = llm_client.create_llm(
        LLMConfig(
            enabled=True,
            api_key="test-key",
            base_url="https://example.test/v1",
            model="test-model",
            timeout_seconds=3,
        )
    )

    response = model.invoke(
        [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user prompt"},
        ],
        max_tokens=600,
    )

    assert response.content == "完整购买意图"
    assert captured["max_tokens"] == 600
