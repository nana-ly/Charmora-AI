"""Build deterministic and LLM-generated replies for the shopping agent."""

from __future__ import annotations

import re
from typing import Any

from agent.negative_feedback_models import NegativeFeedbackApplicationResult
from agent.prompt_loader import load_prompt
from agent.understanding import ActionResult, AgentAction, NoResultsSuggestion
from schemas.chat import ChatMessage
from schemas.product import ProductCard


def build_negative_feedback_noop_reply(
    negative_feedback: NegativeFeedbackApplicationResult | None,
) -> str:
    """Acknowledge repeated negative feedback without claiming a new change."""
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
    """Build a warm deterministic recommendation when LLM copy is unavailable."""
    if negative_feedback and negative_feedback.ack_message:
        lead = negative_feedback.ack_message
    elif current_turn_is_broad:
        target = target_category or "这个品类"
        lead = f"我先按{target}给你挑几款方向不一样的代表商品，方便你继续缩小偏好。"
    else:
        lead = "我按你刚才说的预算、场景和偏好重新筛了一轮。"

    product_lines: list[str] = []
    for index, item in enumerate(items[:3]):
        reason = (item.reason or item.evidence or "匹配你的当前需求").strip()
        if len(reason) > 46:
            reason = f"{reason[:46]}..."
        product_lines.append(
            f"{item.title}大概{_format_price(item.price)}，亮点是{reason} [INSERT:{index}]"
        )

    question = _follow_up_question(target_category, current_turn_is_broad)
    return f"{lead}{''.join(product_lines)}{question}"


def build_explain_reply(action_result: ActionResult) -> str:
    """Explain a recommendation using evidence from the validated product list."""
    index = action_result.target_item_index or 1
    item = action_result.items[index - 1]
    return f"因为{item.evidence}，所以我优先推荐 {item.title}。"


def build_compare_reply(action_result: ActionResult) -> str:
    """Compare two products after CompareTool has validated their indexes."""
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
    """Explain an empty result and offer deterministic relaxation options."""
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
    return "推荐服务暂时不可用，可以稍后重试或放宽条件。"


def build_clarify_reply(question: str | None = None) -> str:
    return question or "可以告诉我想买的品类、预算和最在意的点吗？"


def _build_commerce_reply_legacy(reply_type: str, commerce_state: dict[str, Any] | None) -> str:
    state = commerce_state or {}
    if reply_type == "commerce_error_reply":
        return state.get("message") or "购物车或订单服务暂时不可用，请稍后再试。"
    if reply_type == "cart_updated_reply":
        count = sum(int(item.get("quantity", 0)) for item in state.get("items", []))
        return f"已经加入购物车，现在共有 {count} 件商品，合计 ¥{state.get('total_amount', '0')}。"
    if reply_type == "cart_reply":
        items = state.get("items", [])
        if not items:
            return "购物车还是空的，可以先从推荐商品里挑一款。"
        count = sum(int(item.get("quantity", 0)) for item in items)
        return f"购物车里有 {count} 件商品，当前合计 ¥{state.get('total_amount', '0')}。"
    if reply_type == "order_created_reply":
        return f"模拟订单已创建，订单号是 {state.get('id')}，金额 ¥{state.get('total_amount', '0')}。"
    if reply_type == "checkout_preview_reply":
        count = sum(int(item.get("quantity", 0)) for item in state.get("items", []))
        return (
            f"结算预览已生成：共 {count} 件，合计 ¥{state.get('total_amount', '0')}。"
            "价格和库存已复核；如需继续，请明确回复“确认下单”。"
        )
    if reply_type == "order_cancelled_reply":
        return f"订单 {state.get('id')} 已取消，模拟库存已经回补。"
    if reply_type == "order_status_reply":
        return f"订单 {state.get('id')} 当前状态是 {state.get('status')}，金额 ¥{state.get('total_amount', '0')}。"
    return "购物操作已完成。"


def build_commerce_reply(reply_type: str, commerce_state: dict[str, Any] | None) -> str:
    state = commerce_state or {}
    if reply_type == "commerce_error_reply":
        return state.get("message") or "购物车或订单服务暂时不可用，请稍后再试。"
    if reply_type == "cart_updated_reply":
        count = sum(int(item.get("quantity", 0)) for item in state.get("items", []))
        return f"已经加入购物车，现在共有 {count} 件商品，合计 ¥{state.get('total_amount', '0')}。"
    if reply_type == "cart_reply":
        items = state.get("items", [])
        if not items:
            return "购物车还是空的，可以先从推荐商品里挑一款。"
        count = sum(int(item.get("quantity", 0)) for item in items)
        return f"购物车里有 {count} 件商品，当前合计 ¥{state.get('total_amount', '0')}。"
    if reply_type == "order_created_reply":
        return f"模拟订单已创建，订单号是 {state.get('id')}，金额 ¥{state.get('total_amount', '0')}。"
    if reply_type == "checkout_preview_reply":
        count = sum(int(item.get("quantity", 0)) for item in state.get("items", []))
        return (
            f"结算预览已生成：共 {count} 件，合计 ¥{state.get('total_amount', '0')}。"
            "价格和库存已复核；如需继续，请明确回复“确认下单”。"
        )
    if reply_type == "order_cancelled_reply":
        return f"订单 {state.get('id')} 已取消，模拟库存已经回补。"
    if reply_type == "order_status_reply":
        return f"订单 {state.get('id')} 当前状态是 {state.get('status')}，金额 ¥{state.get('total_amount', '0')}。"
    return "购物操作已完成。"


def build_llm_reply(
    *,
    action_result: ActionResult,
    action: AgentAction,
    purchase_need: str | None,
    messages: list[ChatMessage],
    preferences: dict[str, Any],
    llm_config: Any,
    prompt_version: str = "reply_v1",
) -> tuple[str, list[dict[str, Any]]]:
    """Generate natural copy and convert valid ``[INSERT:n]`` markers to blocks."""
    from llm.client import UniversalChatClient

    if not llm_config or not getattr(llm_config, "is_available", False):
        raise RuntimeError("LLM not available, check LLM_ENABLED and LLM_API_KEY")

    history = "\n".join(
        f"{message.role}: {message.content}"
        for message in messages[-6:]
        if message.content and message.content.strip()
    )
    user_part = (
        f"当前意图: {action.value}\n"
        f"用户需求: {purchase_need or '未明确'}\n"
        f"用户偏好: {preferences}\n"
        f"\n商品数据:\n{_format_items_for_prompt(action_result.items)}\n"
        f"\n—— 对话历史 ——\n{history or '无'}\n"
        "\n请根据以上信息生成自然的中文导购回复。"
    )

    client = UniversalChatClient(llm_config)
    raw = client.generate_reply(
        load_prompt(prompt_version).content,
        user_part,
        temperature=0.3,
        max_tokens=800,
    )
    if not raw or len(raw.strip()) <= 5:
        raise RuntimeError(
            "LLM returned empty. Check the configured API key and endpoint "
            f"({llm_config.base_url})."
        )

    return _parse_content_blocks(raw, action_result.items)


def _parse_content_blocks(
    raw: str,
    items: list[ProductCard],
) -> tuple[str, list[dict[str, Any]]]:
    content_blocks: list[dict[str, Any]] = []
    cursor = 0
    for marker in re.finditer(r"\[INSERT:(\d+)\]", raw):
        text = raw[cursor : marker.start()].strip()
        if text:
            content_blocks.append({"type": "text", "content": text})
        index = int(marker.group(1))
        if 0 <= index < len(items):
            content_blocks.append(
                {"type": "card", "index": index, "item": _item_to_dict(items[index])}
            )
        cursor = marker.end()

    trailing = raw[cursor:].strip()
    if trailing:
        content_blocks.append({"type": "text", "content": trailing})

    clean_text = re.sub(r"\s*\[INSERT:\d+\]\s*", "", raw).strip()
    return clean_text, content_blocks


def _item_to_dict(item: ProductCard) -> dict[str, Any]:
    return item.model_dump()


def _format_items_for_prompt(items: list[ProductCard]) -> str:
    lines = [
        f"- {item.brand} {item.title} | ¥{item.price:g} | "
        f"评分:{item.rating} | 销量:{item.sold_count} | "
        f"推荐理由:{item.reason} | 依据:{item.evidence}"
        for item in items
    ]
    return "\n".join(lines) if lines else "无"


def _format_price(price: float) -> str:
    return f"¥{int(price)}" if float(price).is_integer() else f"¥{price:.2f}"


def _follow_up_question(target_category: str | None, is_broad: bool) -> str:
    if is_broad:
        return "你更看重价格、品牌，还是具体使用场景？"
    target = target_category or "这类商品"
    if "手机" in target:
        return "你更想继续往拍照、续航，还是性价比方向收窄？"
    if any(term in target for term in ("护肤", "面霜", "洗面奶")):
        return "你的肤质和最想解决的问题是什么？我可以再细筛。"
    if "耳机" in target:
        return "你更在意降噪、佩戴舒适，还是通勤续航？"
    return "你想再按预算、品牌，还是使用场景继续细化？"
