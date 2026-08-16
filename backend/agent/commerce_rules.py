from __future__ import annotations

import re

from agent.memory import ConversationState
from agent.understanding import UserIntent, UserUnderstanding

_ORDER_ID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,36}\b")
_ARABIC_INDEX = re.compile(r"第?\s*(\d+)\s*(?:个|件|款)")
_CHINESE_INDEXES = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5}


def commerce_understanding(
    message: str, conversation: ConversationState
) -> UserUnderstanding | None:
    text = message.strip()
    order_match = _ORDER_ID.search(text)
    order_id = order_match.group(0) if order_match else None

    if any(term in text for term in ("查看购物车", "看看购物车", "购物车里", "我的购物车")):
        return _understanding(UserIntent.VIEW_CART)
    if any(term in text for term in ("结算", "提交订单", "确认下单", "现在下单", "确认支付", "确认购买")):
        confirmed = any(term in text for term in ("确认下单", "确认支付", "确认购买"))
        return _understanding(UserIntent.CHECKOUT, checkout_confirmed=confirmed)
    if "取消订单" in text or ("取消" in text and (order_id or conversation.last_order_id)):
        return _understanding(
            UserIntent.CANCEL_ORDER,
            order_id=order_id or conversation.last_order_id,
        )
    if any(term in text for term in ("订单状态", "查订单", "查看订单")):
        return _understanding(
            UserIntent.ORDER_STATUS,
            order_id=order_id or conversation.last_order_id,
        )
    if any(term in text for term in ("加入购物车", "加到购物车", "加购", "放购物车")):
        index = _item_index(text) or conversation.target_item_index or 1
        quantity_match = re.search(r"(?:买|加|要)\s*(\d+)\s*(?:个|件|份|台)", text)
        quantity = int(quantity_match.group(1)) if quantity_match else 1
        return _understanding(
            UserIntent.ADD_TO_CART,
            target_item_index=index,
            quantity=min(max(quantity, 1), 99),
        )
    return None


def _item_index(text: str) -> int | None:
    match = _ARABIC_INDEX.search(text)
    if match:
        return int(match.group(1))
    match = re.search(r"第([一二两三四五])(?:个|件|款)", text)
    return _CHINESE_INDEXES.get(match.group(1)) if match else None


def _understanding(intent: UserIntent, **values) -> UserUnderstanding:
    return UserUnderstanding(intent=intent, confidence=0.95, **values)
