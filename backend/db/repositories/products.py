from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from decimal import Decimal

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from db.models import Inventory, Product, ProductPrice, ProductSku, VectorSyncJob


class ProductRepository:
    """All ORM access for catalog facts lives behind this repository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, product_id: UUID) -> Product | None:
        return self.session.scalar(self._with_details().where(Product.id == product_id))

    def list(
        self,
        *,
        category_id: UUID | None = None,
        active_only: bool = True,
        offset: int = 0,
        limit: int = 50,
        query: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock: bool | None = None,
        sort: str = "newest",
    ) -> list[Product]:
        statement = self._filtered(
            category_id=category_id,
            active_only=active_only,
            query=query,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
        )
        order = {
            "newest": Product.created_at.desc(),
            "price_asc": self._minimum_price_subquery().asc(),
            "price_desc": self._minimum_price_subquery().desc(),
            "title": Product.title.asc(),
        }.get(sort, Product.created_at.desc())
        statement = statement.order_by(order)
        return list(self.session.scalars(statement.offset(offset).limit(limit)).unique())

    def count(
        self,
        *,
        category_id: UUID | None = None,
        active_only: bool = True,
        query: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        in_stock: bool | None = None,
    ) -> int:
        statement = self._filtered(
            category_id=category_id,
            active_only=active_only,
            query=query,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
            details=False,
        ).with_only_columns(func.count(Product.id)).order_by(None)
        return int(self.session.scalar(statement) or 0)

    def _filtered(
        self,
        *,
        category_id: UUID | None,
        active_only: bool,
        query: str | None,
        min_price: Decimal | None,
        max_price: Decimal | None,
        in_stock: bool | None,
        details: bool = True,
    ) -> Select[tuple[Product]]:
        statement = self._with_details() if details else select(Product)
        if category_id:
            statement = statement.where(Product.category_id == category_id)
        if active_only:
            statement = statement.where(Product.active.is_(True))
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            statement = statement.where(
                or_(Product.title.ilike(pattern), Product.brand.ilike(pattern), Product.description.ilike(pattern))
            )
        price = ProductPrice.amount
        sku_match = (
            select(ProductSku.id)
            .join(ProductPrice, ProductPrice.sku_id == ProductSku.id)
            .where(ProductSku.product_id == Product.id, ProductSku.active.is_(True))
        )
        if min_price is not None:
            sku_match = sku_match.where(price >= min_price)
        if max_price is not None:
            sku_match = sku_match.where(price <= max_price)
        if in_stock is True:
            sku_match = sku_match.join(Inventory, Inventory.sku_id == ProductSku.id).where(
                Inventory.available_quantity > 0
            )
        if min_price is not None or max_price is not None or in_stock is True:
            statement = statement.where(exists(sku_match))
        return statement

    @staticmethod
    def _minimum_price_subquery():
        return (
            select(func.min(ProductPrice.amount))
            .join(ProductSku, ProductSku.id == ProductPrice.sku_id)
            .where(ProductSku.product_id == Product.id, ProductSku.active.is_(True))
            .scalar_subquery()
        )

    def eligible_by_ids(self, product_ids: list[UUID]) -> list[Product]:
        """Return only currently sellable DB-backed products, preserving caller order."""
        if not product_ids:
            return []
        now = datetime.now(timezone.utc)
        statement = (
            self._with_details()
            .join(Product.skus)
            .join(ProductSku.inventory)
            .join(ProductSku.prices)
            .where(
                Product.id.in_(product_ids),
                Product.active.is_(True),
                ProductSku.active.is_(True),
                Inventory.available_quantity > 0,
                ProductPrice.valid_from <= now,
                or_(ProductPrice.valid_to.is_(None), ProductPrice.valid_to > now),
            )
        )
        products = list(self.session.scalars(statement).unique())
        by_id = {product.id: product for product in products}
        return [by_id[product_id] for product_id in product_ids if product_id in by_id]

    def pending_sync_jobs(self, limit: int = 100) -> list[VectorSyncJob]:
        statement = (
            select(VectorSyncJob)
            .where(VectorSyncJob.status == "pending")
            .order_by(VectorSyncJob.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(self.session.scalars(statement))

    def claim_sync_jobs(self, limit: int = 100) -> list[UUID]:
        jobs = self.pending_sync_jobs(limit)
        for job in jobs:
            job.status = "processing"
            job.attempts += 1
        self.session.flush()
        return [job.id for job in jobs]

    @staticmethod
    def _with_details() -> Select[tuple[Product]]:
        return select(Product).options(
            selectinload(Product.images),
            selectinload(Product.category),
            selectinload(Product.source),
            selectinload(Product.skus).selectinload(ProductSku.inventory),
            selectinload(Product.skus).selectinload(ProductSku.prices),
        )
