from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from core.config import DatabaseConfig
from core.errors import AppError
from db.models import Inventory, Product, ProductPrice, ProductSku, VectorSyncJob
from db.session import create_database_runtime
from retrieval.database_vector import DatabaseBackedVectorRetriever
from schemas.imports import ProductImportRecord, ProductSkuImport
from services.commerce_service import CommerceService
from services.product_import_service import ProductImportService

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required"
)


def _scoped_url(url: str, schema: str) -> str:
    return make_url(url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(
        hide_password=False
    )


@pytest.fixture(scope="module")
def postgres_runtime():
    base_url = os.environ["TEST_DATABASE_URL"]
    schema = f"shopguide_test_{uuid4().hex}"
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    url = _scoped_url(base_url, schema)
    alembic = Config("alembic.ini")
    alembic.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic, "head")
    runtime = create_database_runtime(DatabaseConfig(url=url))
    try:
        yield runtime, alembic
    finally:
        runtime.engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def _record(key: str, *, stock: int = 5, active: bool = True) -> ProductImportRecord:
    return ProductImportRecord(
        external_id=f"product-{key}",
        title=f"Product {key}",
        category="Integration",
        active=active,
        skus=[
            ProductSkuImport(
                external_id=f"sku-{key}",
                name="Default",
                price=Decimal("19.90"),
                inventory=stock,
            )
        ],
    )


def _import(runtime, key: str, *, stock: int = 5, active: bool = True):
    with runtime.session_factory() as session:
        ProductImportService(session).import_records(
            source_key=f"source-{key}",
            source_name="Integration source",
            source_type="test",
            filename=None,
            records=[_record(key, stock=stock, active=active)],
        )
        product = session.scalar(select(Product).where(Product.external_id == f"product-{key}"))
        sku = session.scalar(select(ProductSku).where(ProductSku.product_id == product.id))
        return product.id, sku.id


def test_alembic_revision_and_reversible_schema(postgres_runtime):
    runtime, alembic = postgres_runtime
    runtime.check_connection()
    runtime.check_migration("20260816_0002")
    command.downgrade(alembic, "base")
    command.upgrade(alembic, "head")
    runtime.check_migration("20260816_0002")


def test_import_is_idempotent_and_writes_outbox(postgres_runtime):
    runtime, _ = postgres_runtime
    first_id, _ = _import(runtime, "idempotent")
    second_id, _ = _import(runtime, "idempotent")

    with runtime.session_factory() as session:
        assert first_id == second_id
        products = list(session.scalars(select(Product).where(Product.id == first_id)))
        jobs = list(session.scalars(select(VectorSyncJob).where(VectorSyncJob.product_id == first_id)))
        assert len(products) == 1
        assert len(jobs) == 2


def test_checkout_rollback_and_cancel_restock_even_after_downlist(postgres_runtime):
    runtime, _ = postgres_runtime
    product_id, sku_id = _import(runtime, "cancel", stock=2)
    with runtime.session_factory() as session:
        CommerceService(session).add_item("cancel-session", sku_id, 2)
    with runtime.session_factory() as session:
        order = CommerceService(session).checkout("cancel-session")

    with runtime.session_factory() as session:
        product = session.get(Product, product_id)
        product.active = False
        session.commit()
    with runtime.session_factory() as session:
        cancelled = CommerceService(session).cancel_order(order.id)
        assert cancelled.status == "cancelled"
    with runtime.session_factory() as session:
        assert session.get(Inventory, sku_id).available_quantity == 2


def test_concurrent_checkout_cannot_oversell(postgres_runtime):
    runtime, _ = postgres_runtime
    _, sku_id = _import(runtime, "concurrent", stock=1)
    for owner in ("buyer-a", "buyer-b"):
        with runtime.session_factory() as session:
            CommerceService(session).add_item(owner, sku_id, 1)

    def checkout(owner: str) -> str:
        with runtime.session_factory() as session:
            try:
                CommerceService(session).checkout(owner)
                return "created"
            except AppError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(checkout, ("buyer-a", "buyer-b")))

    assert outcomes.count("created") == 1
    assert outcomes.count("insufficient_inventory") == 1
    with runtime.session_factory() as session:
        assert session.get(Inventory, sku_id).available_quantity == 0


def test_vector_candidates_are_filtered_through_postgresql(postgres_runtime):
    runtime, _ = postgres_runtime
    valid_id, _ = _import(runtime, "truth-valid", stock=2)
    inactive_id, _ = _import(runtime, "truth-inactive", stock=2, active=False)
    empty_id, _ = _import(runtime, "truth-empty", stock=0)
    expired_id, expired_sku_id = _import(runtime, "truth-expired", stock=2)
    with runtime.session_factory() as session:
        price = session.scalar(
            select(ProductPrice).where(
                ProductPrice.sku_id == expired_sku_id,
                ProductPrice.valid_to.is_(None),
            )
        )
        price.valid_to = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()

    missing_id = uuid4()

    class FakeStore:
        def query_by_text(self, query: str, top_k: int):
            return [
                {"product_id": str(value), "score": 0.9 - index * 0.1}
                for index, value in enumerate(
                    (valid_id, inactive_id, empty_id, expired_id, missing_id)
                )
            ]

    retriever = DatabaseBackedVectorRetriever(FakeStore(), runtime)
    results, count = retriever.search_truth(
        "integration", filters={}, negative_filters=None, top_k=10
    )

    assert count == 1
    assert [UUID(result.product["product_id"]) for result in results] == [valid_id]
