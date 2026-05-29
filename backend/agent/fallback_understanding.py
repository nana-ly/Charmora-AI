"""LLM 输出不可用时的保守理解兜底。"""

from __future__ import annotations

import logging

from agent.category_rules import (
    catalog_category_for,
    detect_target_category,
    extract_preference_hints,
    has_broad_category_signal,
    has_purchase_signal,
    is_standalone_category_term,
)
from agent.memory import ConversationState
from agent.negative_feedback_rules import (
    clean_positive_purchase_need,
    extract_negative_updates,
)
from agent.understanding import UserIntent, UserUnderstanding

logger = logging.getLogger(__name__)


LOWER_PRICE_FEEDBACK_TERMS = (
    "太贵",
    "贵了",
    "便宜点",
    "便宜一点",
    "更便宜",
    "预算低一点",
    "预算低",
    "不要这么贵",
    "价格低一点",
    "便宜一些",
)

HIGHER_PRICE_ALLOWANCE_TERMS = (
    "贵一点也行",
    "贵的也可以",
    "不怕贵",
    "不贵了",
    "价格高点没关系",
    "高一点没关系",
)


def _has_active_purchase_context(conversation: ConversationState) -> bool:
    return bool(
        conversation.purchase_need
        or conversation.preferences.get("target_category")
        or conversation.last_items
    )


def _is_lower_price_feedback(message: str) -> bool:
    if any(term in message for term in HIGHER_PRICE_ALLOWANCE_TERMS):
        return False
    return any(term in message for term in LOWER_PRICE_FEEDBACK_TERMS)


def _contextual_price_feedback(
    *,
    message: str,
    conversation: ConversationState,
    reason: str,
) -> UserUnderstanding | None:
    if not _has_active_purchase_context(conversation):
        return None
    if not _is_lower_price_feedback(message):
        return None

    updates: dict[str, object] = {
        "price_direction": "lower",
        "avoid_current_price_band": True,
    }
    target_category = conversation.preferences.get("target_category")
    category = conversation.preferences.get("category")
    if isinstance(target_category, str) and target_category:
        updates["target_category"] = target_category
    if isinstance(category, str) and category:
        updates["category"] = category

    logger.info(
        "understanding source=fallback reason=%s intent=update_preference target_category=%s",
        reason,
        target_category,
    )
    return UserUnderstanding(
        intent=UserIntent.UPDATE_PREFERENCE,
        confidence=0.6,
        purchase_need=conversation.purchase_need,
        preference_updates=updates,
    )


def _has_positive_constraints(hints: dict[str, object]) -> bool:
    return any(
        key in hints
        for key in ("budget", "brand", "focus", "usage", "preferred_brands")
    )


def _purchase_request_understanding(
    *,
    message: str,
    reason: str,
    negative_updates: dict[str, object] | None = None,
) -> UserUnderstanding | None:
    target = detect_target_category(message)
    if target is None:
        return None

    hints = extract_preference_hints(message)
    negative_updates = negative_updates or {}
    positive_purchase_need = clean_positive_purchase_need(message, negative_updates)
    if not positive_purchase_need and target.target_category:
        positive_purchase_need = target.target_category
    has_negative_updates = bool(negative_updates)

    is_broad = (
        (
            has_broad_category_signal(message)
            or is_standalone_category_term(message, target)
        )
        and not _has_positive_constraints(hints)
    )
    has_clean_positive_target = bool(positive_purchase_need)
    if (
        not has_purchase_signal(message)
        and not is_broad
        and not (has_clean_positive_target and has_negative_updates)
    ):
        return None

    updates = {
        "target_category": target.target_category,
        "category": target.catalog_category
        or catalog_category_for(target.target_category),
        "canonical_target_key": target.canonical_target_key,
        **hints,
    }
    updates["is_broad_category_request"] = bool(is_broad)

    logger.info(
        "understanding source=fallback reason=%s intent=recommend target_category=%s",
        reason,
        target.target_category,
    )
    return UserUnderstanding(
        intent=UserIntent.RECOMMEND,
        confidence=0.55,
        purchase_need=positive_purchase_need,
        preference_updates={
            key: value for key, value in updates.items() if value is not None
        },
        negative_updates=negative_updates,
    )


def fallback_understanding(
    *,
    message: str,
    conversation: ConversationState,
    reason: str,
) -> UserUnderstanding | None:
    negative_updates = extract_negative_updates(message)

    purchase_request = _purchase_request_understanding(
        message=message,
        reason=reason,
        negative_updates=negative_updates,
    )
    if purchase_request is not None:
        return purchase_request

    if negative_updates:
        logger.info(
            "understanding source=fallback reason=%s intent=update_preference negative_updates=%s",
            reason,
            sorted(negative_updates),
        )
        return UserUnderstanding(
            intent=UserIntent.UPDATE_PREFERENCE,
            confidence=0.65,
            purchase_need=conversation.purchase_need,
            preference_updates={},
            negative_updates=negative_updates,
        )

    contextual = _contextual_price_feedback(
        message=message,
        conversation=conversation,
        reason=reason,
    )
    if contextual is not None:
        return contextual

    return None
