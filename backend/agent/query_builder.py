"""推荐查询构建器。"""

from __future__ import annotations

from typing import Any

from agent.memory import ConversationState

_NEGATIVE_BRAND_MARKERS = ("不要", "不买", "不考虑", "排除", "别要", "避开")
_PURCHASE_NEED_SEPARATORS = ("，", ",", "。", "；", ";", "\n")


def build_recommendation_query(conversation: ConversationState) -> str:
    """用结构化记忆补全推荐查询，避免只依赖用户原话。"""
    if not conversation.purchase_need:
        return ""

    preferences = conversation.preferences
    purchase_need = _clean_negative_brand_fragments(
        conversation.purchase_need,
        conversation.excluded_brands,
    )
    structured_price_limit = _format_price_limit(preferences)
    if structured_price_limit and structured_price_limit not in purchase_need:
        query_parts = [structured_price_limit, purchase_need]
    else:
        query_parts = [purchase_need]
    query = _join_query(query_parts)

    _append_missing(query_parts, query, preferences.get("target_category"))
    query = _join_query(query_parts)
    _append_missing(query_parts, query, preferences.get("category"))
    query = _join_query(query_parts)
    _append_missing(query_parts, query, structured_price_limit)
    query = _join_query(query_parts)
    _append_values(query_parts, query, preferences.get("brand"))
    query = _join_query(query_parts)
    _append_values(query_parts, query, preferences.get("preferred_brands"))
    query = _join_query(query_parts)
    _append_values(query_parts, query, preferences.get("focus"))
    query = _join_query(query_parts)

    has_lower_price_direction = (
        preferences.get("price_direction") == "lower"
        or preferences.get("price_preference") == "lower"
    )
    if has_lower_price_direction:
        query = _append_lower_price_direction(
            query_parts,
            query,
            avoid_current_price_band=bool(
                preferences.get("avoid_current_price_band")
            ),
        )

    return _join_query(query_parts)


def _clean_negative_brand_fragments(purchase_need: str, excluded_brands: list[str]) -> str:
    brands = [brand.strip() for brand in excluded_brands if brand.strip()]
    if not brands:
        return purchase_need

    fragments = _split_purchase_need(purchase_need)
    kept = [
        fragment
        for fragment in fragments
        if not _is_negative_brand_fragment(fragment, brands)
    ]
    return _join_query(kept) if kept else purchase_need


def _split_purchase_need(purchase_need: str) -> list[str]:
    fragments = [purchase_need]
    for separator in _PURCHASE_NEED_SEPARATORS:
        next_fragments: list[str] = []
        for fragment in fragments:
            next_fragments.extend(fragment.split(separator))
        fragments = next_fragments
    return [fragment.strip() for fragment in fragments if fragment.strip()]


def _is_negative_brand_fragment(fragment: str, brands: list[str]) -> bool:
    return any(marker in fragment for marker in _NEGATIVE_BRAND_MARKERS) and any(
        brand in fragment for brand in brands
    )


def _format_budget(value: Any) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return f"预算{value}以内"
    return str(value).strip() or None


def _format_price_limit(preferences: dict[str, Any]) -> str | None:
    budget = preferences.get("budget")
    max_price = preferences.get("max_price")

    if isinstance(budget, bool):
        budget = None
    if isinstance(max_price, bool):
        max_price = None

    if isinstance(budget, int) and isinstance(max_price, int):
        return _format_budget(min(budget, max_price))
    if isinstance(max_price, int):
        return _format_budget(max_price)
    return _format_budget(budget)


def _append_values(parts: list[str], query: str, value: Any) -> None:
    for item in _as_values(value):
        _append_missing(parts, query, item)
        query = _join_query(parts)


def _append_missing(parts: list[str], query: str, value: Any) -> None:
    text = str(value).strip() if value is not None else ""
    if text and text not in query:
        parts.append(text)


def _append_lower_price_direction(
    parts: list[str],
    query: str,
    *,
    avoid_current_price_band: bool,
) -> str:
    for value in ("价格更低", "性价比优先"):
        _append_missing(parts, query, value)
        query = _join_query(parts)

    if avoid_current_price_band:
        _append_missing(parts, query, "避免上一轮同价位")
        query = _join_query(parts)

    return query


def _as_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _unique_values(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    return [text] if text else []


def _unique_values(values) -> list[str]:
    merged: list[str] = []
    for value in values:
        if value not in merged:
            merged.append(value)
    return merged


def _join_query(parts: list[str]) -> str:
    return "，".join(parts)
