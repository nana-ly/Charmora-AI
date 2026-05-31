"""负向偏好更新的确定性解析规则。"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from agent.category_rules import BRAND_TERMS

_CHINESE_INDEX_NUMBER = "一二三四五六七八九十两"
NegativeFeedbackUpdates = dict[str, Any]


def extract_negative_updates(message: str) -> dict[str, Any]:
    text = message.strip()
    if not text:
        return {}

    if any(term in text for term in ("这几个都不要", "这些都不要")):
        return {"exclude_all_last_items": True}

    cancel_item_removal = _extract_cancel_item_index_removal(text)
    if cancel_item_removal:
        return {
            "remove_excluded_item_indexes": [cancel_item_removal],
            "unsupported_negative_type": "remove_item_index",
        }

    chinese_item_exclusion = _extract_chinese_item_index_exclusion(text)
    if chinese_item_exclusion:
        return {"excluded_item_indexes": [chinese_item_exclusion]}

    item_exclusion = _extract_item_index_exclusion(text)
    if item_exclusion:
        return {"excluded_item_indexes": [item_exclusion]}

    if _extract_current_item_reference_exclusion(text):
        return {"excluded_item_reference": "current"}

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


def _negative_phrase_patterns() -> Sequence[str]:
    brand_names = "|".join(re.escape(brand) for brand in BRAND_TERMS)
    return (
        r"(?:不要|不买|不考虑|排除)\s*第\s*\d+\s*[个款]?",
        r"第\s*\d+\s*[个款]?\s*(?:不要|不买|不考虑|排除)",
        rf"(?:不要|排除|不考虑)\s*第\s*[{_CHINESE_INDEX_NUMBER}]+\s*[个款]?",
        rf"第\s*[{_CHINESE_INDEX_NUMBER}]+\s*[个款]?\s*(?:不要|排除|不考虑)",
        r"(?:不要|排除|不考虑)\s*(?:这个|这个商品|刚才那个|刚刚那个)",
        r"(?:这个|这个商品|刚才那个|刚刚那个)\s*(?:不要|排除|不考虑)",
        r"(?:这几个都不要|这些都不要)",
        rf"(?:不要|不买|不考虑|排除|别要|避开)\s*(?:{brand_names})",
        rf"(?:{brand_names})\s*(?:(?:也)?(?:可以|行)\s*)?(?:不要|不买|不考虑|排除)",
    )


def _remove_negative_phrases(text: str) -> str:
    cleaned = text
    for pattern in _negative_phrase_patterns():
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"[，,、；;]\s*[，,、；;]+", "，", cleaned)
    cleaned = cleaned.strip(" ，,、；;\n\t")
    return cleaned.strip()


def clean_positive_purchase_need(
    text: str,
    negative_updates: NegativeFeedbackUpdates | None = None,
) -> str:
    if negative_updates and (
        negative_updates.get("unsupported_negative_type")
        or any(key.startswith("remove_") for key in negative_updates)
    ):
        return text.strip()
    return _remove_negative_phrases(text)


def _extract_item_index_removal(text: str) -> int | None:
    patterns = (r"第\s*(\d+)\s*[个款]?\s*(?:也可以|可以|也行|行)",)
    return _first_index_match(text, patterns)


def _extract_cancel_item_index_removal(text: str) -> int | None:
    return _first_index_match(text, (r"取消排除\s*第\s*(\d+)\s*[个款]?",))


_CHINESE_INDEX_VALUES = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _parse_chinese_index(value: str) -> int | None:
    value = value.strip()
    if value in _CHINESE_INDEX_VALUES:
        return _CHINESE_INDEX_VALUES[value]
    if value.startswith("十") and len(value) == 2:
        suffix = _CHINESE_INDEX_VALUES.get(value[1])
        return 10 + suffix if suffix else None
    if value.endswith("十") and len(value) == 2:
        prefix = _CHINESE_INDEX_VALUES.get(value[0])
        return prefix * 10 if prefix else None
    if "十" in value and len(value) == 3:
        prefix = _CHINESE_INDEX_VALUES.get(value[0])
        suffix = _CHINESE_INDEX_VALUES.get(value[2])
        return prefix * 10 + suffix if prefix and suffix else None
    return None


def _extract_chinese_item_index_exclusion(text: str) -> int | None:
    chinese_index = rf"第\s*([{_CHINESE_INDEX_NUMBER}]+)\s*[个款]?"
    patterns = (
        rf"(?:不要|排除|不考虑)\s*{chinese_index}",
        rf"{chinese_index}\s*(?:不要|排除|不考虑)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return _parse_chinese_index(match.group(1))
    return None


def _extract_item_index_exclusion(text: str) -> int | None:
    patterns = (
        r"(?:不要|排除|不考虑)\s*第\s*(\d+)\s*[个款]?",
        r"第\s*(\d+)\s*[个款]?\s*(?:不要|排除|不考虑)",
    )
    return _first_index_match(text, patterns)


def _extract_current_item_reference_exclusion(text: str) -> bool:
    return bool(
        re.search(r"(?:不要|排除|不考虑)\s*(?:这个|这个商品|刚才那个|刚刚那个)", text)
        or re.search(r"(?:这个|这个商品|刚才那个|刚刚那个)\s*(?:不要|排除|不考虑)", text)
    )


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
