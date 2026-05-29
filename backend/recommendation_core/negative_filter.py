"""Negative filtering helpers for recommendation candidates and results."""

from typing import Any

from schemas.recommend import NegativeFilters


def normalize_brand_key(value: str) -> str:
    return value.strip().casefold()


def has_negative_filters(negative_filters: NegativeFilters | None) -> bool:
    if negative_filters is None:
        return False
    return bool(
        negative_filters.excluded_product_ids
        or negative_filters.excluded_brands
    )


def passes_negative_filter(
    product: dict[str, Any],
    negative_filters: NegativeFilters | None,
) -> bool:
    if not has_negative_filters(negative_filters):
        return True
    assert negative_filters is not None

    if product.get("product_id") in set(negative_filters.excluded_product_ids):
        return False

    excluded_brand_keys = {
        normalize_brand_key(brand)
        for brand in negative_filters.excluded_brands
    }
    product_brand = product.get("brand")
    if isinstance(product_brand, str):
        return normalize_brand_key(product_brand) not in excluded_brand_keys

    return True


def apply_negative_filters(
    products: list[dict[str, Any]],
    negative_filters: NegativeFilters | None,
) -> list[dict[str, Any]]:
    if not has_negative_filters(negative_filters):
        return products
    return [
        product
        for product in products
        if passes_negative_filter(product, negative_filters)
    ]
