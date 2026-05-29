"""Helpers for applying negative feedback to conversation state."""

from typing import Any

from agent.memory import ConversationState
from agent.negative_feedback_models import (
    NegativeFeedbackApplicationResult,
    NegativeFeedbackItem,
)
from schemas.product import ProductCard
from schemas.recommend import NegativeFilters


def normalize_brand_key(value: str) -> str:
    return value.strip().casefold()


def migrate_legacy_excluded_brands(conversation: ConversationState) -> None:
    legacy_brands = conversation.preferences.pop("excluded_brands", None)
    if not isinstance(legacy_brands, list):
        return

    merged = list(conversation.excluded_brands)
    seen = {
        normalize_brand_key(brand)
        for brand in merged
        if isinstance(brand, str) and normalize_brand_key(brand)
    }
    for brand in legacy_brands:
        if not isinstance(brand, str):
            continue
        normalized = normalize_brand_key(brand)
        if not normalized or normalized in seen:
            continue
        merged.append(brand.strip())
        seen.add(normalized)

    conversation.excluded_brands = merged


def build_negative_filters(conversation: ConversationState) -> NegativeFilters:
    return NegativeFilters(
        excluded_product_ids=list(conversation.excluded_product_ids),
        excluded_brands=list(conversation.excluded_brands),
        excluded_keywords=list(conversation.excluded_keywords),
        excluded_price_ranges=list(conversation.excluded_price_ranges),
    )


def apply_negative_feedback(
    conversation: ConversationState,
    negative_updates: dict[str, Any] | None,
    *,
    catalog_products: list[ProductCard | dict[str, Any]],
) -> NegativeFeedbackApplicationResult:
    migrate_legacy_excluded_brands(conversation)

    if not negative_updates:
        return NegativeFeedbackApplicationResult()

    if "unsupported_negative_type" in negative_updates:
        return NegativeFeedbackApplicationResult(
            detected=True,
            noop=True,
            noop_reason="unsupported_negative_type",
            ack_message="暂不支持这种排除方式，我会继续按当前需求筛选。",
        )

    if "excluded_item_indexes" in negative_updates:
        return _apply_item_index_exclusion(conversation, negative_updates)

    if negative_updates.get("remove_excluded_brands"):
        return _apply_remove_excluded_brand(
            conversation,
            negative_updates,
            catalog_products,
        )

    if negative_updates.get("excluded_brands"):
        return _apply_brand_exclusion(conversation, negative_updates, catalog_products)

    return NegativeFeedbackApplicationResult()


def _apply_item_index_exclusion(
    conversation: ConversationState,
    negative_updates: dict[str, Any],
) -> NegativeFeedbackApplicationResult:
    items = conversation.last_successful_items or conversation.last_items
    index = _first_int(negative_updates.get("excluded_item_indexes"))

    if index is None:
        return NegativeFeedbackApplicationResult(
            detected=True,
            needs_clarification=True,
            invalid_reason="missing_item_index",
            clarifying_question=f"上一轮只有 {len(items)} 款商品，你想排除第几款？",
        )

    if not items:
        return NegativeFeedbackApplicationResult(
            detected=True,
            needs_clarification=True,
            invalid_reason="missing_last_successful_items",
            clarifying_question="我还没有上一轮可排除的推荐结果，可以先告诉我想买什么。",
        )

    if index < 1 or index > len(items):
        return NegativeFeedbackApplicationResult(
            detected=True,
            needs_clarification=True,
            clarifying_question=f"上一轮只有 {len(items)} 款商品，你想排除第几款？",
        )

    item = items[index - 1]
    if item.product_id in conversation.excluded_product_ids:
        return NegativeFeedbackApplicationResult(
            detected=True,
            noop=True,
            noop_reason="already_excluded",
            target_product_ids=[item.product_id],
        )

    conversation.excluded_product_ids.append(item.product_id)
    conversation.negative_feedback_items.append(
        NegativeFeedbackItem(
            product_id=item.product_id,
            title=item.title,
            brand=item.brand,
            price=item.price,
        )
    )

    return NegativeFeedbackApplicationResult(
        detected=True,
        applied=True,
        ack_message=f"已排除第 {index} 款，我按你的需求重新筛选。",
        changed_fields=["excluded_product_ids", "negative_feedback_items"],
        target_product_ids=[item.product_id],
    )


def _apply_remove_excluded_brand(
    conversation: ConversationState,
    negative_updates: dict[str, Any],
    catalog_products: list[ProductCard | dict[str, Any]],
) -> NegativeFeedbackApplicationResult:
    brand = _resolve_brand(
        _first_str(negative_updates.get("remove_excluded_brands")),
        [*conversation.excluded_brands, *_catalog_brands(catalog_products)],
    )
    if not brand:
        return NegativeFeedbackApplicationResult(
            detected=True,
            noop=True,
            noop_reason="not_currently_excluded",
        )

    normalized = normalize_brand_key(brand)
    if not any(normalize_brand_key(existing) == normalized for existing in conversation.excluded_brands):
        return NegativeFeedbackApplicationResult(
            detected=True,
            noop=True,
            noop_reason="not_currently_excluded",
            target_brands=[brand],
        )

    conversation.excluded_brands = [
        existing
        for existing in conversation.excluded_brands
        if normalize_brand_key(existing) != normalized
    ]
    _remove_positive_brand_preferences(conversation, brand)

    return NegativeFeedbackApplicationResult(
        detected=True,
        removed=True,
        changed_fields=["excluded_brands", "preferences"],
        target_brands=[brand],
        ack_message=f"已恢复考虑{brand}，我按你的需求重新筛选。",
    )


def _apply_brand_exclusion(
    conversation: ConversationState,
    negative_updates: dict[str, Any],
    catalog_products: list[ProductCard | dict[str, Any]],
) -> NegativeFeedbackApplicationResult:
    brand = _resolve_brand(
        _first_str(negative_updates.get("excluded_brands")),
        [
            *conversation.excluded_brands,
            *_last_successful_item_brands(conversation),
            *_catalog_brands(catalog_products),
        ],
    )
    if not brand:
        return NegativeFeedbackApplicationResult(
            detected=True,
            needs_clarification=True,
            invalid_reason="unknown_brand",
        )

    if not _has_active_purchase_context(conversation):
        return NegativeFeedbackApplicationResult(
            detected=True,
            needs_clarification=True,
            clarifying_question=f"可以，想买什么品类时排除{brand}？",
        )

    normalized = normalize_brand_key(brand)
    if any(normalize_brand_key(existing) == normalized for existing in conversation.excluded_brands):
        return NegativeFeedbackApplicationResult(
            detected=True,
            noop=True,
            noop_reason="already_excluded",
            target_brands=[brand],
        )

    conversation.excluded_brands.append(brand)
    _remove_positive_brand_preferences(conversation, brand)
    conversation.negative_feedback_items.append(NegativeFeedbackItem(brand=brand))

    return NegativeFeedbackApplicationResult(
        detected=True,
        applied=True,
        ack_message=f"已排除{brand}，我按你的需求重新筛选。",
        changed_fields=["excluded_brands", "preferences", "negative_feedback_items"],
        target_brands=[brand],
    )


def _remove_positive_brand_preferences(
    conversation: ConversationState,
    brand: str,
) -> None:
    normalized = normalize_brand_key(brand)
    if normalize_brand_key(str(conversation.preferences.get("brand", ""))) == normalized:
        conversation.preferences.pop("brand", None)

    preferred_brands = conversation.preferences.get("preferred_brands")
    if isinstance(preferred_brands, list):
        remaining = [
            preferred
            for preferred in preferred_brands
            if not isinstance(preferred, str)
            or normalize_brand_key(preferred) != normalized
        ]
        conversation.preferences["preferred_brands"] = remaining

    conversation.preferences.pop("excluded_brands", None)


def _has_active_purchase_context(conversation: ConversationState) -> bool:
    if conversation.purchase_need:
        return True
    return any(
        isinstance(conversation.preferences.get(key), str)
        and conversation.preferences[key].strip()
        for key in ("target_category", "category")
    )


def _resolve_brand(candidate: str | None, authoritative_brands: list[str]) -> str | None:
    if not candidate:
        return None
    normalized = normalize_brand_key(candidate)
    if not normalized:
        return None
    for brand in authoritative_brands:
        if isinstance(brand, str) and normalize_brand_key(brand) == normalized:
            return brand.strip()
    return None


def _first_int(values: Any) -> int | None:
    if not isinstance(values, list) or not values:
        return None
    value = values[0]
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _first_str(values: Any) -> str | None:
    if not isinstance(values, list) or not values:
        return None
    value = values[0]
    return value if isinstance(value, str) else None


def _last_successful_item_brands(conversation: ConversationState) -> list[str]:
    return [
        item.brand
        for item in conversation.last_successful_items
        if isinstance(item.brand, str)
    ]


def _catalog_brands(catalog_products: list[ProductCard | dict[str, Any]]) -> list[str]:
    brands: list[str] = []
    for product in catalog_products:
        if isinstance(product, dict):
            brand = product.get("brand")
        else:
            brand = product.brand
        if isinstance(brand, str):
            brands.append(brand)
    return brands
