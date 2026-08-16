from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from db.models import Category, Product, ProductPrice, ProductSku
from db.repositories.products import ProductRepository
from schemas.catalog import ProductSkuView, ProductView


class CatalogNotFoundError(LookupError):
    pass


class CatalogService:
    def __init__(self, repository: ProductRepository) -> None:
        self.repository = repository

    def list_products(
        self, *, category_id: UUID | None, active_only: bool, offset: int, limit: int,
        query: str | None = None, min_price: Decimal | None = None,
        max_price: Decimal | None = None, in_stock: bool | None = None,
        sort: str = "newest",
    ) -> list[ProductView]:
        return [
            self.to_view(product)
            for product in self.repository.list(
                category_id=category_id,
                active_only=active_only,
                offset=offset,
                limit=limit,
                query=query,
                min_price=min_price,
                max_price=max_price,
                in_stock=in_stock,
                sort=sort,
            )
        ]

    def count_products(self, **filters) -> int:
        return self.repository.count(**filters)

    def list_categories(self):
        from schemas.catalog import CategoryView

        rows = self.repository.session.execute(
            select(Category, func.count(Product.id))
            .outerjoin(Product, (Product.category_id == Category.id) & Product.active.is_(True))
            .where(Category.active.is_(True))
            .group_by(Category.id)
            .order_by(Category.name)
        )
        return [CategoryView(id=category.id, external_key=category.external_key, name=category.name, product_count=count) for category, count in rows]

    def get_product(self, product_id: UUID) -> ProductView:
        product = self.repository.get(product_id)
        if product is None:
            raise CatalogNotFoundError(str(product_id))
        return self.to_view(product)

    @classmethod
    def to_view(cls, product: Product) -> ProductView:
        return ProductView(
            id=product.id,
            external_id=product.external_id,
            category_id=product.category_id,
            category_name=product.category.name,
            source_key=product.source.key,
            title=product.title,
            brand=product.brand,
            description=product.description,
            attributes=product.attributes,
            active=product.active,
            images=[image.url for image in sorted(product.images, key=lambda value: value.position)],
            skus=[cls._sku_view(sku) for sku in product.skus],
        )

    @staticmethod
    def _sku_view(sku: ProductSku) -> ProductSkuView:
        current = _current_price(sku.prices)
        inventory = sku.inventory
        return ProductSkuView(
            id=sku.id,
            external_id=sku.external_id,
            name=sku.name,
            attributes=sku.attributes,
            active=sku.active,
            available_quantity=inventory.available_quantity if inventory else 0,
            price=current.amount if current else None,
            currency=current.currency if current else "CNY",
        )


def _current_price(prices: list[ProductPrice]) -> ProductPrice | None:
    now = datetime.now(timezone.utc)
    valid = [
        price
        for price in prices
        if _aware(price.valid_from) <= now
        and (price.valid_to is None or _aware(price.valid_to) > now)
    ]
    return max(valid, key=lambda price: _aware(price.valid_from), default=None)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
