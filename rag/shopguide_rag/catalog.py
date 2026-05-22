from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProductRecord:
    product_id: str
    title: str
    brand: str
    category: str
    sub_category: str
    base_price: float
    image_path: str
    skus: list[dict[str, Any]]
    rag_knowledge: dict[str, Any]
    source_file: Path


def iter_product_files(dataset_root: Path) -> list[Path]:
    return sorted(dataset_root.glob("*/data/*.json"))


def load_products(dataset_root: Path) -> list[ProductRecord]:
    products: list[ProductRecord] = []
    for file_path in iter_product_files(dataset_root):
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        products.append(
            ProductRecord(
                product_id=payload["product_id"],
                title=payload["title"],
                brand=payload["brand"],
                category=payload["category"],
                sub_category=payload["sub_category"],
                base_price=float(payload["base_price"]),
                image_path=payload["image_path"],
                skus=payload.get("skus", []),
                rag_knowledge=payload.get("rag_knowledge", {}),
                source_file=file_path,
            )
        )
    return products


def load_product_map(dataset_root: Path) -> dict[str, ProductRecord]:
    return {product.product_id: product for product in load_products(dataset_root)}


def build_product_document(product: ProductRecord) -> str:
    sku_summary = _build_sku_summary(product)
    faq_summary = _build_faq_summary(product)
    marketing = _compact_text(product.rag_knowledge.get("marketing_description", ""))
    sections = [
        f"商品ID：{product.product_id}",
        f"标题：{product.title}",
        f"品牌：{product.brand}",
        f"类目：{product.category}",
        f"子类目：{product.sub_category}",
        f"价格区间：{_price_min(product)}-{_price_max(product)}",
        f"规格摘要：{sku_summary}",
        f"营销描述：{marketing}",
        f"FAQ摘要：{faq_summary}",
    ]
    return "\n".join(section for section in sections if section)


def product_metadata(product: ProductRecord) -> dict[str, str | float | int | bool]:
    property_options = _collect_property_options(product)
    review_count = len(product.rag_knowledge.get("user_reviews", []))
    faq_count = len(product.rag_knowledge.get("official_faq", []))

    return {
        "product_id": product.product_id,
        "title": product.title,
        "brand": product.brand,
        "category": product.category,
        "sub_category": product.sub_category,
        "category_path": f"{product.category}/{product.sub_category}",
        "base_price": product.base_price,
        "price_min": _price_min(product),
        "price_max": _price_max(product),
        "sku_count": len(product.skus),
        "faq_count": faq_count,
        "review_count": review_count,
        "avg_rating": _average_rating(product),
        "has_faq": faq_count > 0,
        "has_reviews": review_count > 0,
        "sku_keys": "|".join(sorted(property_options)),
        "sku_property_summary": _build_sku_summary(product),
        "capacity_options": _join_options(property_options.get("容量", [])),
        "color_options": _join_options(property_options.get("颜色", [])),
        "storage_options": _join_options(property_options.get("存储", [])),
        "version_options": _join_options(property_options.get("版本", [])),
        "flavor_options": _join_options(property_options.get("口味", [])),
        "quantity_options": _join_options(property_options.get("数量", [])),
        "package_options": _join_options(property_options.get("包装", [])),
        "image_path": product.image_path,
        "source_file": str(product.source_file),
    }


def _price_min(product: ProductRecord) -> float:
    prices = [float(sku.get("price", product.base_price)) for sku in product.skus]
    return min(prices, default=product.base_price)


def _price_max(product: ProductRecord) -> float:
    prices = [float(sku.get("price", product.base_price)) for sku in product.skus]
    return max(prices, default=product.base_price)


def _average_rating(product: ProductRecord) -> float:
    ratings = [
        int(review["rating"])
        for review in product.rag_knowledge.get("user_reviews", [])
        if "rating" in review
    ]
    if not ratings:
        return 0.0
    return round(sum(ratings) / len(ratings), 2)


def _collect_property_options(product: ProductRecord) -> dict[str, set[str]]:
    options: dict[str, set[str]] = {}
    for sku in product.skus:
        for key, value in sku.get("properties", {}).items():
            options.setdefault(key, set()).add(str(value))
    return options


def _join_options(options: set[str]) -> str:
    return "|".join(sorted(options))


def _build_sku_summary(product: ProductRecord) -> str:
    property_options = _collect_property_options(product)
    if not property_options:
        return ""

    summary_parts = [
        f"{key}:{'|'.join(sorted(values))}" for key, values in sorted(property_options.items())
    ]
    return "；".join(summary_parts)


def _build_faq_summary(product: ProductRecord) -> str:
    summary_parts: list[str] = []
    for faq in product.rag_knowledge.get("official_faq", []):
        question = _compact_text(faq.get("question", ""))
        answer = _compact_text(faq.get("answer", ""))
        if question or answer:
            summary_parts.append(f"{question} {answer}".strip())
    return " ".join(summary_parts)


def _compact_text(value: str) -> str:
    return " ".join(value.split())
