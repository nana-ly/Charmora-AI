"""导购 Agent 的确定性中文回复构造。"""

from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.understanding import ActionResult, NoResultsSuggestion
from schemas.product import ProductCard


def build_negative_feedback_noop_reply(
    negative_feedback: NegativeFeedbackApplicationResult | None,
) -> str:
    """构造负反馈重复或无变更时的确认文案。"""
    if negative_feedback and negative_feedback.noop_reason == "already_excluded":
        return "已经排除过这个条件了，我会继续按当前排除条件筛选。"
    if negative_feedback and negative_feedback.ack_message:
        return negative_feedback.ack_message
    return "收到，我会继续按当前条件筛选。"


def build_recommendation_reply(
    *,
    items: list[ProductCard],
    negative_feedback: NegativeFeedbackApplicationResult | None = None,
    current_turn_is_broad: bool = False,
    target_category: str | None = None,
) -> str:
    """构造推荐成功文案，保留泛品类和负反馈确认分支。"""
    if negative_feedback and negative_feedback.ack_message:
        return (
            f"{negative_feedback.ack_message}"
            "我根据你的需求筛选了这几款商品，可以先看第一款的匹配理由。"
        )
    if current_turn_is_broad:
        target = target_category or "这个品类"
        return f"我先按{target}这个品类给你挑几款代表商品，你可以再告诉我预算、品牌或使用场景。"
    return "我根据你的需求筛选了这几款商品，可以先看第一款的匹配理由。"


def build_explain_reply(action_result: ActionResult) -> str:
    """基于上一轮真实商品证据生成解释文案。"""
    index = action_result.target_item_index or 1
    item = action_result.items[index - 1]
    return f"因为{item.evidence}，所以我优先推荐 {item.title}。"


def build_compare_reply(action_result: ActionResult) -> str:
    """基于 CompareTool 校验后的两个商品生成对比文案。"""
    first_index, second_index = action_result.compare_item_indexes[:2]
    first_item = action_result.items[first_index - 1]
    second_item = action_result.items[second_index - 1]

    if first_item.price < second_item.price:
        recommendation = f"如果预算更有限，{first_item.title} 更合适，因为价格更低。"
    elif second_item.price < first_item.price:
        recommendation = f"如果预算更有限，{second_item.title} 更合适，因为价格更低。"
    else:
        recommendation = "两款价格接近，可以优先按上面的证据和使用重点来选。"

    return (
        f"{first_item.title}：价格 {first_item.price}，依据是{first_item.evidence}。"
        f"{second_item.title}：价格 {second_item.price}，依据是{second_item.evidence}。"
        f"{recommendation}"
    )


def build_no_results_reply(suggestion: NoResultsSuggestion | None) -> str:
    """构造无结果分支文案，并给出可放宽条件。"""
    if suggestion is None:
        return "我暂时没有找到完全匹配的商品。你可以放宽预算、品牌或品类条件。"

    options = "、".join(suggestion.relax_options)
    blockers = "、".join(suggestion.blocking_constraints)
    if blockers:
        return (
            f"我暂时没有找到完全满足“{suggestion.purchase_need}”的商品。"
            f"主要限制可能是{blockers}。你可以选择{options}。"
        )
    return (
        f"我暂时没有找到完全满足“{suggestion.purchase_need}”的商品。"
        f"你可以选择{options}。"
    )


def build_tool_error_reply() -> str:
    """推荐工具不可用时的稳定错误文案。"""
    return "推荐服务暂时不可用，可以稍后重试或放宽条件。"


def build_clarify_reply(question: str | None = None) -> str:
    """构造澄清回复。"""
    return question or "可以告诉我想买的品类、预算和最在意的点吗？"
