from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from db.base import Base
import db.models  # noqa: F401
from db.models import Product
from db.session import DatabaseRuntime
from services.import_parsers import parse_product_file_result
from services.product_import_service import ProductImportService


def bootstrap_demo_catalog(runtime: DatabaseRuntime) -> int:
    """Create the local SQLite schema and seed the bundled synthetic catalog once."""
    Base.metadata.create_all(runtime.engine)
    with runtime.session_factory() as session:
        if (session.scalar(select(func.count(Product.id))) or 0) > 0:
            return 0

        catalog = (
            Path(__file__).resolve().parents[2]
            / "ecommerce_agent_dataset"
            / "synthetic_lifestyle_v1"
            / "products.json"
        )
        parsed = parse_product_file_result(catalog.read_bytes(), catalog.name)
        if parsed.errors:
            raise RuntimeError(f"bundled demo catalog is invalid: {parsed.errors[:3]}")
        batch = ProductImportService(session).import_records(
            source_key="synthetic-lifestyle-v1",
            source_name="绮饰集模拟商品 v1",
            source_type="synthetic",
            filename=catalog.name,
            records=parsed.records,
        )
        return batch.success_count
