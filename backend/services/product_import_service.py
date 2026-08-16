from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import (
    Category,
    DataSource,
    ImportBatch,
    Inventory,
    Product,
    ProductImage,
    ProductPrice,
    ProductSku,
    VectorSyncJob,
)
from schemas.imports import ImportBatchView, ProductImportRecord


class ProductImportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def import_records(
        self,
        *,
        source_key: str,
        source_name: str,
        source_type: str,
        filename: str | None,
        records: list[ProductImportRecord],
        parse_errors: list[dict] | None = None,
        total_count: int | None = None,
    ) -> ImportBatchView:
        source = self._source(source_key, source_name, source_type)
        batch = ImportBatch(
            source_id=source.id,
            filename=filename,
            status="running",
            total_count=total_count if total_count is not None else len(records),
            failure_count=len(parse_errors or []),
        )
        self.session.add(batch)
        self.session.commit()

        errors: list[dict] = list(parse_errors or [])
        for index, record in enumerate(records):
            try:
                with self.session.begin_nested():
                    self._upsert_product(source, batch, record)
                batch.success_count += 1
            except Exception as exc:
                errors.append(
                    {"row": index + 1, "external_id": record.external_id, "message": str(exc)}
                )
                batch.failure_count += 1
        batch.errors = errors
        batch.status = "completed" if not errors else "completed_with_errors"
        batch.completed_at = datetime.now(timezone.utc)
        self.session.commit()
        return self.to_view(batch, source.key)

    def list_batches(
        self, *, status: str | None = None, offset: int = 0, limit: int = 50
    ) -> list[ImportBatchView]:
        statement = select(ImportBatch).order_by(ImportBatch.created_at.desc())
        if status:
            statement = statement.where(ImportBatch.status == status)
        batches = list(self.session.scalars(statement.offset(offset).limit(limit)))
        source_ids = {batch.source_id for batch in batches}
        sources = {
            source.id: source.key
            for source in self.session.scalars(select(DataSource).where(DataSource.id.in_(source_ids)))
        }
        return [self.to_view(batch, sources.get(batch.source_id, "unknown")) for batch in batches]

    def get_batch(self, batch_id: UUID) -> ImportBatchView | None:
        batch = self.session.get(ImportBatch, batch_id)
        if batch is None:
            return None
        source = self.session.get(DataSource, batch.source_id)
        return self.to_view(batch, source.key if source else "unknown")

    def _source(self, key: str, name: str, source_type: str) -> DataSource:
        source = self.session.scalar(select(DataSource).where(DataSource.key == key))
        if source is None:
            source = DataSource(
                key=key,
                name=name,
                source_type=source_type,
                authorized=source_type != "crawler",
            )
            self.session.add(source)
            self.session.flush()
        return source

    def _category(self, name: str) -> Category:
        key = name.strip().lower().replace(" ", "_")
        category = self.session.scalar(select(Category).where(Category.external_key == key))
        if category is None:
            category = Category(external_key=key, name=name)
            self.session.add(category)
            self.session.flush()
        return category

    def _upsert_product(
        self, source: DataSource, batch: ImportBatch, record: ProductImportRecord
    ) -> Product:
        category = self._category(record.category)
        product = self.session.scalar(
            select(Product).where(
                Product.source_id == source.id,
                Product.external_id == record.external_id,
            )
        )
        operation = "upsert"
        if product is None:
            product = Product(
                source_id=source.id,
                category_id=category.id,
                external_id=record.external_id,
                title=record.title,
            )
            self.session.add(product)
            self.session.flush()
        product.category_id = category.id
        product.title = record.title
        product.brand = record.brand
        product.description = record.description
        product.attributes = {
            **record.attributes,
            **({"sub_category": record.sub_category} if record.sub_category else {}),
        }
        product.active = record.active
        product.import_batch_id = batch.id

        existing_skus = {sku.external_id: sku for sku in product.skus}
        incoming_skus: set[str] = set()
        for incoming in record.skus:
            incoming_skus.add(incoming.external_id)
            sku = existing_skus.get(incoming.external_id)
            if sku is None:
                sku = ProductSku(product=product, external_id=incoming.external_id)
                self.session.add(sku)
            sku.name = incoming.name
            sku.attributes = incoming.attributes
            sku.active = incoming.active
            if sku.inventory is None:
                sku.inventory = Inventory(available_quantity=incoming.inventory)
            else:
                sku.inventory.available_quantity = incoming.inventory
                sku.inventory.version += 1
            for price in sku.prices:
                if price.valid_to is None:
                    price.valid_to = datetime.now(timezone.utc)
            sku.prices.append(ProductPrice(amount=incoming.price, currency="CNY"))
        for external_id, sku in existing_skus.items():
            if external_id not in incoming_skus:
                sku.active = False

        product.images.clear()
        product.images.extend(
            ProductImage(url=url, position=index)
            for index, url in enumerate(record.image_urls)
        )
        self.session.add(
            VectorSyncJob(
                product_id=product.id,
                operation=operation if record.active else "delete",
                status="pending",
            )
        )
        return product

    @staticmethod
    def to_view(batch: ImportBatch, source_key: str) -> ImportBatchView:
        return ImportBatchView(
            id=batch.id,
            source_key=source_key,
            filename=batch.filename,
            status=batch.status,
            total_count=batch.total_count,
            success_count=batch.success_count,
            failure_count=batch.failure_count,
            errors=batch.errors,
            created_at=batch.created_at,
            completed_at=batch.completed_at,
        )
