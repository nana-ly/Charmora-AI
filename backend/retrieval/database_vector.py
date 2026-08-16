from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from db.models import Product, ProductPrice
from db.repositories.products import ProductRepository
from db.session import DatabaseRuntime
from recommendation_core.negative_filter import passes_negative_filter
from retrieval.base import RetrievalResult, Retriever
from schemas.recommend import NegativeFilters


class DatabaseBackedVectorRetriever(Retriever):
    """Use Chroma for IDs and PostgreSQL for every user-visible product fact."""

    def __init__(self, store: Any, database: DatabaseRuntime) -> None:
        self.store = store
        self.database = database

    def search(self, query: str, candidates=None, top_k: int = 3) -> list[RetrievalResult]:
        results, _ = self.search_truth(query, filters={}, negative_filters=None, top_k=top_k)
        return results

    def search_truth(
        self,
        query: str,
        *,
        filters: dict[str, Any],
        negative_filters: NegativeFilters | None,
        top_k: int,
    ) -> tuple[list[RetrievalResult], int]:
        raw = self.store.query_by_text(query, top_k=max(top_k * 8, 30))
        raw_by_id = {str(row.get("product_id")): row for row in raw}
        ids: list[UUID] = []
        for row in raw:
            try:
                ids.append(UUID(str(row.get("product_id"))))
            except (TypeError, ValueError):
                continue
        with self.database.session_factory() as session:
            products = ProductRepository(session).eligible_by_ids(ids)
            product_dicts = [self._to_legacy(product) for product in products]
        filtered = [
            product
            for product in product_dicts
            if _matches_filters(product, filters)
            and passes_negative_filter(product, negative_filters)
        ]
        results: list[RetrievalResult] = []
        for product in filtered[:top_k]:
            row = raw_by_id[str(product["product_id"])]
            results.append(
                RetrievalResult(
                    product=product,
                    evidence=f"向量召回后经 PostgreSQL 库存与价格校验，相似度 {float(row.get('score') or 0):.2f}。",
                    score=float(row.get("score") or 0),
                    rank=len(results) + 1,
                    source="postgresql",
                    retriever_mode="database_vector",
                    score_type="vector_similarity",
                    metadata={"truth_source": "postgresql"},
                )
            )
        return results, len(filtered)

    @staticmethod
    def _to_legacy(product: Product) -> dict[str, Any]:
        sellable = [sku for sku in product.skus if sku.active and sku.inventory and sku.inventory.available_quantity > 0]
        priced = [(sku, _current_price(sku.prices)) for sku in sellable]
        priced = [(sku, price) for sku, price in priced if price is not None]
        sku, price = min(priced, key=lambda value: value[1].amount)
        return {
            "product_id": str(product.id),
            "sku_id": str(sku.id),
            "title": product.title,
            "brand": product.brand,
            "category": product.category.name,
            "sub_category": product.attributes.get("sub_category", ""),
            "base_price": float(price.amount),
            "image_path": product.images[0].url if product.images else "",
            "rag_knowledge": {"marketing_description": product.description},
            "attributes": product.attributes,
        }


def _matches_filters(product: dict[str, Any], filters: dict[str, Any]) -> bool:
    category = filters.get("category")
    if category and product.get("category") not in {category, "食品饮料" if category == "食品生活" else category}:
        return False
    brand = filters.get("brand")
    if brand and brand not in str(product.get("brand", "")):
        return False
    max_price = filters.get("max_price")
    return not (max_price is not None and float(product.get("base_price", 0)) > float(max_price))


def _current_price(prices: list[ProductPrice]) -> ProductPrice | None:
    now = datetime.now(timezone.utc)
    valid = [price for price in prices if _aware(price.valid_from) <= now and (price.valid_to is None or _aware(price.valid_to) > now)]
    return max(valid, key=lambda value: _aware(value.valid_from), default=None)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
