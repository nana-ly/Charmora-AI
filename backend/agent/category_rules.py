"""LLM 理解层周围的小型确定性规则。"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel


class TargetCategoryMatch(BaseModel):
    target_category: str
    catalog_category: str | None = None
    matched_text: str
    canonical_target_key: str


TARGET_CATEGORY_ALIASES: Sequence[tuple[str, str, str, str]] = tuple(
    sorted(
        (
            ("护肤产品", "护肤产品", "美妆护肤", "skin_care"),
            ("护肤品", "护肤品", "美妆护肤", "skin_care"),
            ("化妆品", "护肤品", "美妆护肤", "skin_care"),
            ("笔记本", "笔记本", "数码电子", "laptop"),
            ("防晒", "防晒", "美妆护肤", "skin_care"),
            ("面霜", "面霜", "美妆护肤", "skin_care"),
            ("护肤", "护肤", "美妆护肤", "skin_care"),
            ("美妆", "护肤品", "美妆护肤", "skin_care"),
            ("手机", "手机", "数码电子", "phone"),
            ("耳机", "耳机", "数码电子", "headphones"),
            ("电脑", "电脑", "数码电子", "computer"),
            ("平板", "平板", "数码电子", "tablet"),
            ("咖啡", "咖啡", "食品生活", "coffee"),
            ("饮品", "饮品", "食品生活", "beverage"),
            ("T恤", "T恤", "服饰运动", "t_shirt"),
            ("外套", "外套", "服饰运动", "jacket"),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

PURCHASE_SIGNALS = (
    "想买",
    "要买",
    "买一台",
    "买一个",
    "买一只",
    "推荐",
    "看看",
    "预算",
    "以内",
    "不超过",
    "主要",
    "适合",
)

FOCUS_TERMS = (
    "拍照",
    "续航",
    "降噪",
    "办公",
    "游戏",
    "通勤",
    "学生",
    "敏感肌",
    "保湿",
    "抗初老",
    "低糖",
    "冷萃",
    "速干",
    "凉快",
)

BRAND_TERMS = ("华为", "小米", "苹果", "荣耀", "OPPO", "vivo", "三星")
RESTORE_CONTEXT_TERMS = ("之前", "恢复", "按之前", "就之前")
RESTORE_ACTION_TERMS = ("恢复之前", "按之前", "就之前")
CONFIRMATION_PREFIXES = ("对", "是的", "可以")
SHORT_CONFIRMATIONS = ("对", "是", "是的", "可以", "嗯", "嗯嗯", "好", "好的")
REJECTION_TERMS = ("不是", "不用", "不要之前", "不用之前", "算了", "重新")


def detect_target_category(message: str) -> TargetCategoryMatch | None:
    for alias, target_category, catalog_category, key in TARGET_CATEGORY_ALIASES:
        if alias in message:
            return TargetCategoryMatch(
                target_category=target_category,
                catalog_category=catalog_category,
                matched_text=alias,
                canonical_target_key=key,
            )
    return None


def canonical_target_key(
    target_category: str | None,
    catalog_category: str | None = None,
) -> str | None:
    if not target_category and not catalog_category:
        return None
    for _, canonical, catalog, key in TARGET_CATEGORY_ALIASES:
        if target_category == canonical:
            return key
    if target_category:
        for alias, _, _, key in TARGET_CATEGORY_ALIASES:
            if target_category == alias:
                return key
    return None


def catalog_category_for(target_category: str) -> str | None:
    for _, canonical, catalog_category, _ in TARGET_CATEGORY_ALIASES:
        if canonical == target_category:
            return catalog_category
    return None


def has_purchase_signal(message: str) -> bool:
    return any(term in message for term in PURCHASE_SIGNALS)


def extract_preference_hints(message: str) -> dict[str, object]:
    hints: dict[str, object] = {}

    budget_match = re.search(
        r"(?:预算)?\s*(\d{3,6})\s*(?:元)?\s*(?:以内|以下|不超过)?",
        message,
    )
    if budget_match and any(term in message for term in ("预算", "以内", "以下", "不超过")):
        hints["budget"] = int(budget_match.group(1))

    for brand in BRAND_TERMS:
        if brand in message and not _is_negative_brand_mention(message, brand):
            hints["brand"] = brand
            break

    focus = [term for term in FOCUS_TERMS if term in message]
    if focus:
        hints["focus"] = focus

    return hints


def _is_negative_brand_mention(message: str, brand: str) -> bool:
    escaped = re.escape(brand)
    negative_before_brand = any(
        re.search(rf"{prefix}\s*{escaped}", message)
        for prefix in ("不要", "不买", "不考虑", "排除")
    )
    brand_before_negative = re.search(
        rf"{escaped}\s*(?:(?:也)?\s*(?:可以|行)\s*)?(?:也)?\s*(?:不要|不买|不考虑|排除)",
        message,
    )
    return bool(negative_before_brand or brand_before_negative)


def is_restore_confirmation(message: str) -> bool:
    if is_restore_rejection(message):
        return False

    text = message.strip()
    if text in SHORT_CONFIRMATIONS:
        return True

    if not any(term in text for term in RESTORE_CONTEXT_TERMS):
        return False

    if any(term in text for term in RESTORE_ACTION_TERMS):
        return True

    return any(text.startswith(prefix) for prefix in CONFIRMATION_PREFIXES)


def is_restore_rejection(message: str) -> bool:
    return any(term in message for term in REJECTION_TERMS)
