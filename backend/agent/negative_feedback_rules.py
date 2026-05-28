"""Deterministic parsing rules for negative preference updates."""

from __future__ import annotations

import re
from typing import Any

from agent.category_rules import BRAND_TERMS

_CHINESE_INDEX_NUMBER = "一二三四五六七八九十两"


def extract_negative_updates(message: str) -> dict[str, Any]:
    text = message.strip()
    if not text:
        return {}

    if any(term in text for term in ("这几个都不要", "这些都不要")):
        return {"unsupported_negative_type": "bulk_item_exclusion"}

    cancel_item_removal = _extract_cancel_item_index_removal(text)
    if cancel_item_removal:
        return {
            "remove_excluded_item_indexes": [cancel_item_removal],
            "unsupported_negative_type": "remove_item_index",
        }

    if _has_chinese_item_index_exclusion(text):
        return {"unsupported_negative_type": "item_index_chinese_number"}

    item_exclusion = _extract_item_index_exclusion(text)
    if item_exclusion:
        return {"excluded_item_indexes": [item_exclusion]}

    item_removal = _extract_item_index_removal(text)
    if item_removal:
        return {
            "remove_excluded_item_indexes": [item_removal],
            "unsupported_negative_type": "remove_item_index",
        }

    cancel_removed_brand = _extract_cancel_brand_removal(text)
    if cancel_removed_brand:
        return {"remove_excluded_brands": [cancel_removed_brand]}

    excluded_brand = _extract_brand_exclusion(text)
    if excluded_brand:
        return {"excluded_brands": [excluded_brand]}

    removed_brand = _extract_brand_removal(text)
    if removed_brand:
        return {"remove_excluded_brands": [removed_brand]}

    return {}


def _extract_item_index_removal(text: str) -> int | None:
    patterns = (r"第\s*(\d+)\s*[个款]?\s*(?:也可以|可以|也行|行)",)
    return _first_index_match(text, patterns)


def _extract_cancel_item_index_removal(text: str) -> int | None:
    return _first_index_match(text, (r"取消排除\s*第\s*(\d+)\s*[个款]?",))


def _has_chinese_item_index_exclusion(text: str) -> bool:
    chinese_index = rf"第\s*[{_CHINESE_INDEX_NUMBER}]+\s*[个款]?"
    return bool(
        re.search(rf"(?:不要|排除|不考虑)\s*{chinese_index}", text)
        or re.search(rf"{chinese_index}\s*(?:不要|排除|不考虑)", text)
    )


def _extract_item_index_exclusion(text: str) -> int | None:
    patterns = (
        r"(?:不要|排除|不考虑)\s*第\s*(\d+)\s*[个款]?",
        r"第\s*(\d+)\s*[个款]?\s*(?:不要|排除|不考虑)",
    )
    return _first_index_match(text, patterns)


def _first_index_match(text: str, patterns: tuple[str, ...]) -> int | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _extract_brand_removal(text: str) -> str | None:
    for brand in BRAND_TERMS:
        if re.search(rf"{re.escape(brand)}\s*(?:也可以|可以|也行|行)", text):
            return brand
    return None


def _extract_cancel_brand_removal(text: str) -> str | None:
    for brand in BRAND_TERMS:
        if re.search(rf"取消排除\s*{re.escape(brand)}", text):
            return brand
    return None


def _extract_brand_exclusion(text: str) -> str | None:
    for brand in BRAND_TERMS:
        escaped = re.escape(brand)
        if re.search(rf"(?:不要|不买|不考虑|排除)\s*{escaped}", text):
            return brand

    for brand in BRAND_TERMS:
        escaped = re.escape(brand)
        if re.search(
            rf"{escaped}\s*(?:(?:也)?\s*(?:可以|行)\s*)?(?:也)?\s*(?:不要|不买|不考虑|排除)",
            text,
        ):
            return brand
    return None
