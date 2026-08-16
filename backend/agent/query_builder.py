"""Build a positive, structured recommendation query from conversation state."""

from __future__ import annotations

from typing import Any

from agent.memory import ConversationState
from agent.negative_feedback_rules import clean_positive_purchase_need

_NEGATIVE_MARKERS = ("不要", "不买", "不考虑", "排除", "别要", "避开")
_SEPARATORS = ("，", ",", "。", "；", ";", "\n")


def build_recommendation_query(conversation: ConversationState) -> str:
    """Merge positive free text with verified structured target/preferences."""
    preferences = conversation.preferences
    purchase_need = clean_positive_purchase_need(conversation.purchase_need or "")
    purchase_need = _remove_negative_brand_fragments(
        purchase_need, conversation.excluded_brands
    )
    if not purchase_need:
        purchase_need = str(
            preferences.get("target_category") or preferences.get("category") or ""
        ).strip()

    price_limit = _price_limit(preferences)
    parts: list[str] = []
    if price_limit and price_limit not in purchase_need:
        parts.append(price_limit)
    _append(parts, purchase_need)
    for value in (
        preferences.get("target_category"),
        preferences.get("category"),
        price_limit,
        preferences.get("brand"),
        preferences.get("preferred_brands"),
        preferences.get("focus"),
    ):
        for item in _values(value):
            _append(parts, item)

    if preferences.get("price_direction") == "lower" or preferences.get(
        "price_preference"
    ) == "lower":
        _append(parts, "价格更低")
        _append(parts, "性价比优先")
        if preferences.get("avoid_current_price_band"):
            _append(parts, "避免上一轮同价位")
    return "，".join(parts)


def _remove_negative_brand_fragments(text: str, excluded_brands: list[str]) -> str:
    fragments = [text]
    for separator in _SEPARATORS:
        fragments = [piece for fragment in fragments for piece in fragment.split(separator)]
    brands = [brand.strip() for brand in excluded_brands if brand.strip()]
    kept = [
        fragment.strip()
        for fragment in fragments
        if fragment.strip()
        and not (
            any(marker in fragment for marker in _NEGATIVE_MARKERS)
            and any(brand in fragment for brand in brands)
        )
    ]
    return "，".join(kept)


def _price_limit(preferences: dict[str, Any]) -> str | None:
    numeric = [
        value
        for value in (preferences.get("budget"), preferences.get("max_price"))
        if isinstance(value, int) and not isinstance(value, bool)
    ]
    if numeric:
        return f"预算{min(numeric)}以内"
    budget = preferences.get("budget")
    if budget is not None and not isinstance(budget, bool):
        return str(budget).strip() or None
    return None


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _append(parts: list[str], value: str | None) -> None:
    text = str(value).strip() if value is not None else ""
    query = "，".join(parts)
    if text and text not in query:
        parts.append(text)
