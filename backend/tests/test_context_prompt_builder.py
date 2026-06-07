from schemas.chat import ChatMessage
from schemas.product import ProductCard


def test_prompt_context_builder_includes_current_context_and_last_items():
    from agent.context_prompt_builder import PromptContextBuilder
    from agent.memory import ConversationState

    conversation = ConversationState(
        session_id="prompt-context",
        purchase_need="预算9000以内的手机",
        preferences={
            "target_category": "手机",
            "category": "数码电子",
            "canonical_target_key": "phone",
            "budget": 9000,
        },
        excluded_brands=["苹果"],
        last_items=[
            ProductCard(
                product_id="p1",
                title="测试手机",
                brand="华为",
                price=3999,
                reason="匹配预算",
                evidence="命中手机和预算",
            )
        ],
    )
    conversation.messages = [
        ChatMessage(role="user", content=f"历史消息{i}") for i in range(10)
    ]

    block = PromptContextBuilder().build("不要苹果", conversation)

    assert "最新用户消息：不要苹果" in block
    assert "当前 purchase_need：预算9000以内的手机" in block
    assert '"budget": 9000' in block
    assert "排除品牌" in block
    assert "苹果" in block
    assert "测试手机" in block
    assert "历史消息0" not in block
    assert "历史消息9" in block


def test_prompt_context_builder_summarizes_previous_contexts_without_old_items():
    from agent.context_manager import reset_for_new_target
    from agent.context_prompt_builder import PromptContextBuilder
    from agent.memory import ConversationState

    conversation = ConversationState(
        session_id="previous-context",
        purchase_need="预算9000以内的手机",
        preferences={
            "target_category": "手机",
            "category": "数码电子",
            "canonical_target_key": "phone",
            "budget": 9000,
        },
    )
    reset_for_new_target(conversation)
    conversation.purchase_need = "推荐护肤品"
    conversation.preferences = {
        "target_category": "护肤品",
        "category": "美妆护肤",
        "canonical_target_key": "skin_care",
    }

    block = PromptContextBuilder().build("还是看手机吧", conversation)

    assert "previous_purchase_contexts" in block
    assert "target_category=手机" in block
    assert "purchase_need=预算9000以内的手机" in block
    assert "上一轮成功推荐：\n无" in block


def test_prompt_context_builder_limits_items_only_when_configured():
    from agent.context_prompt_builder import PromptContextBuilder
    from agent.memory import ConversationState

    conversation = ConversationState(
        session_id="prompt-context-limits",
        last_items=[
            ProductCard(
                product_id="p1",
                title="手机1",
                brand="华为",
                price=3999,
                reason="匹配",
                evidence="证据一很长很长",
            ),
            ProductCard(
                product_id="p2",
                title="手机2",
                brand="小米",
                price=2999,
                reason="匹配",
                evidence="证据二",
            ),
        ],
    )

    default_block = PromptContextBuilder().build("看看手机", conversation)
    limited_block = PromptContextBuilder(
        last_item_limit=1,
        evidence_max_chars=3,
    ).build("看看手机", conversation)

    assert "手机1" in default_block
    assert "手机2" in default_block
    assert "手机1" in limited_block
    assert "手机2" not in limited_block
    assert "evidence=证据一..." in limited_block
