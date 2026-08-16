"""Migrate, validate and import the ShopGuide Lifestyle demo catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CATALOG = ROOT / "ecommerce_agent_dataset" / "synthetic_lifestyle_v1" / "products.json"
sys.path.insert(0, str(BACKEND))

from api.catalog import database_runtime  # noqa: E402
from core.config import load_app_config  # noqa: E402
from retrieval.vector import VectorRetriever  # noqa: E402
from services.import_parsers import parse_product_file_result  # noqa: E402
from services.product_import_service import ProductImportService  # noqa: E402
from services.vector_sync_service import VectorSyncService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="validate without writing")
    parser.add_argument("--skip-vector", action="store_true", help="leave vector jobs pending")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parsed = parse_product_file_result(CATALOG.read_bytes(), CATALOG.name)
    print(
        f"catalog total={parsed.total_count} valid={len(parsed.records)} "
        f"invalid={len(parsed.errors)}"
    )
    if parsed.errors:
        for error in parsed.errors:
            print(f"row={error['row']} external_id={error['external_id']} error={error['message']}")
        return 1
    if args.dry_run:
        print("dry-run complete; database unchanged")
        return 0

    config = load_app_config()
    alembic = Config(str(BACKEND / "alembic.ini"))
    alembic.set_main_option("sqlalchemy.url", config.database.url)
    command.upgrade(alembic, "head")

    runtime = database_runtime()
    with runtime.session_factory() as session:
        batch = ProductImportService(session).import_records(
            source_key="synthetic-lifestyle-v1",
            source_name="生活杂货模拟数据 v1",
            source_type="synthetic",
            filename=CATALOG.name,
            records=parsed.records,
        )
        print(
            f"import batch={batch.id} status={batch.status} "
            f"success={batch.success_count} failure={batch.failure_count}"
        )

    if not args.skip_vector:
        with runtime.session_factory() as session:
            result = VectorSyncService(session, VectorRetriever().store).process_pending(1000)
            print(f"vector processed={result['processed']} failed={result['failed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
