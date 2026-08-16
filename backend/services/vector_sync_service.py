from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Product, VectorSyncJob
from db.repositories.products import ProductRepository


class ProductVectorIndex(Protocol):
    def upsert_product(
        self, *, product_id: str, document: str, metadata: dict[str, Any]
    ) -> None: ...

    def delete_products(self, product_ids: list[str]) -> None: ...


class VectorSyncService:
    def __init__(self, session: Session, index: ProductVectorIndex) -> None:
        self.session = session
        self.repository = ProductRepository(session)
        self.index = index

    def process_pending(self, limit: int = 100) -> dict[str, int]:
        with self.session.begin():
            job_ids = self.repository.claim_sync_jobs(limit)
        processed = 0
        failed = 0
        for job_id in job_ids:
            job = self.session.get(VectorSyncJob, job_id)
            if job is None:
                continue
            try:
                product = self.repository.get(job.product_id)
                if job.operation == "delete" or product is None or not product.active:
                    self.index.delete_products([str(job.product_id)])
                else:
                    self.index.upsert_product(
                        product_id=str(product.id),
                        document=_document(product),
                        metadata={
                            "product_id": str(product.id),
                            "brand": product.brand,
                            "category": product.category.name,
                            "source": "postgresql",
                        },
                    )
                job.status = "completed"
                job.processed_at = datetime.now(timezone.utc)
                processed += 1
            except Exception as exc:
                job.last_error = str(exc)[:2000]
                job.status = "failed" if job.attempts >= 5 else "pending"
                failed += 1
            self.session.commit()
        return {"processed": processed, "failed": failed, "total": len(job_ids)}

    def retry_failed(self, limit: int = 100) -> int:
        jobs = list(
            self.session.scalars(
                select(VectorSyncJob)
                .where(VectorSyncJob.status == "failed")
                .order_by(VectorSyncJob.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for job in jobs:
            job.status = "pending"
            job.attempts = 0
            job.last_error = None
        self.session.commit()
        return len(jobs)


def _document(product: Product) -> str:
    attributes = " ".join(f"{key}:{value}" for key, value in product.attributes.items())
    return "\n".join(
        value
        for value in (
            product.title,
            f"品牌：{product.brand}" if product.brand else "",
            f"品类：{product.category.name}",
            product.description,
            attributes,
        )
        if value
    )
