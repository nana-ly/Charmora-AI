from agent.memory import ConversationState
from agent.tools import RecommendationTool
from agent.understanding import AgentAction
from schemas.product import ProductCard


def test_action_executor_recommend_success_updates_successful_result_state():
    from agent.graph.action_executor import ActionExecutor

    def recommendation(query: str, top_k: int = 3, negative_filters=None):
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
                    "product_id": "p1",
                    "title": "拍照手机",
                    "brand": "小米",
                    "price": 3999,
                    "reason": "拍照不错",
                    "evidence": "命中拍照",
                }
            ],
        }

    conversation = ConversationState(session_id="executor-success")
    conversation.purchase_need = "预算9000以内的拍照手机"
    conversation.preferences = {"target_category": "手机", "category": "数码电子"}

    result = ActionExecutor(RecommendationTool(recommend_func=recommendation)).execute(
        action=AgentAction.RECOMMEND,
        conversation=conversation,
    )

    assert result.reply_type == "recommendation_reply"
    assert conversation.latest_attempt_status == "success"
    assert conversation.last_result_status == "success"
    assert conversation.last_successful_items[0].product_id == "p1"
    assert conversation.last_successful_result_id is not None


def test_action_executor_no_results_records_relax_options_without_success_overwrite():
    from agent.graph.action_executor import ActionExecutor

    previous = ProductCard(
        product_id="old",
        title="旧手机",
        brand="苹果",
        price=6999,
        reason="旧推荐",
        evidence="旧证据",
    )

    def no_results(query: str, top_k: int = 3, negative_filters=None):
        return {
            "query": query,
            "filters": {
                "category": "数码电子",
                "max_price": 3000,
                "brand": None,
                "keywords": ["手机", "拍照"],
            },
            "items": [],
        }

    conversation = ConversationState(session_id="executor-no-results")
    conversation.purchase_need = "3000以内、拍照强、折叠屏手机"
    conversation.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "budget": 3000,
    }
    conversation.last_successful_items = [previous]
    conversation.last_successful_result_id = "old-result"

    result = ActionExecutor(RecommendationTool(recommend_func=no_results)).execute(
        action=AgentAction.RECOMMEND,
        conversation=conversation,
    )

    assert result.reply_type == "no_results_reply"
    assert conversation.latest_attempt_status == "no_results"
    assert conversation.last_successful_items == [previous]
    assert conversation.last_successful_result_id == "old-result"
    assert "提高预算或放宽价格上限" in result.no_results.relax_options


def test_action_executor_tool_error_keeps_previous_items_and_records_recoverable_error():
    from agent.graph.action_executor import ActionExecutor

    old_item = ProductCard(
        product_id="old",
        title="旧手机",
        brand="苹果",
        price=6999,
        reason="旧推荐",
        evidence="旧证据",
    )

    def failing(query: str, top_k: int = 3, negative_filters=None):
        raise RuntimeError("boom")

    conversation = ConversationState(session_id="executor-error")
    conversation.purchase_need = "手机"
    conversation.last_items = [old_item]
    conversation.last_successful_items = [old_item]

    result = ActionExecutor(RecommendationTool(recommend_func=failing)).execute(
        action=AgentAction.RECOMMEND,
        conversation=conversation,
    )

    assert result.reply_type == "tool_error_reply"
    assert result.tool_error == "recommendation_failed"
    assert conversation.latest_attempt_status == "tool_error"
    assert conversation.last_items == [old_item]
    assert conversation.last_successful_items == [old_item]


def test_action_executor_explain_updates_conversation_target_item_index():
    from agent.graph.action_executor import ActionExecutor
    from agent.understanding import UserIntent, UserUnderstanding

    conversation = ConversationState(session_id="executor-explain")
    conversation.last_items = [
        ProductCard(
            product_id="p1",
            title="手机 1",
            brand="小米",
            price=3999,
            reason="拍照不错",
            evidence="命中拍照",
        )
    ]
    understanding = UserUnderstanding(
        intent=UserIntent.EXPLAIN,
        confidence=0.9,
        target_item_index=1,
    )

    result = ActionExecutor(RecommendationTool(recommend_func=lambda query: {})).execute(
        action=AgentAction.EXPLAIN,
        conversation=conversation,
        understanding=understanding,
    )

    assert result.reply_type == "explain_reply"
    assert conversation.target_item_index == 1
