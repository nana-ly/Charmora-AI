"""推荐查询构建器。"""

from __future__ import annotations

from typing import Any

from agent.memory import ConversationState


def build_recommendation_query(conversation: ConversationState) -> str:
    """用结构化记忆补全推荐查询，避免只依赖用户原话。"""
    if not conversation.purchase_need:
        return ""

    preferences = conversation.preferences
    structured_price_limit = _format_price_limit(preferences)
    if structured_price_limit and structured_price_limit not in conversation.purchase_need:
        query_parts = [structured_price_limit, conversation.purchase_need]
    else:
        query_parts = [conversation.purchase_need]
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
