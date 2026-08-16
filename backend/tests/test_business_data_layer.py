from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
import httpx
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _record():
    return {
        "product_id": "p-test-1",
        "title": "测试咖啡",
        "brand": "测试品牌",
        "category": "食品饮料",
        "base_price": 39.9,
        "image_path": "images/test.jpg",
        "skus": [
            {
                "sku_id": "sku-test-1",
                "properties": {"规格": "10包"},
                "price": 35.5,
                "stock": 12,
            }
        ],
        "rag_knowledge": {"marketing_description": "适合办公室饮用"},
    }


def test_json_import_parser_normalizes_dataset_shape():
    from services.import_parsers import parse_product_file

    parsed = parse_product_file(json.dumps(_record(), ensure_ascii=False).encode(), "one.json")

    assert parsed[0].external_id == "p-test-1"
    assert parsed[0].description == "适合办公室饮用"
    assert parsed[0].skus[0].external_id == "sku-test-1"
    assert parsed[0].skus[0].inventory == 12


def test_csv_import_parser_supports_json_sku_column():
    from services.import_parsers import parse_product_file

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["product_id", "title", "category", "skus"])
    writer.writeheader()
    writer.writerow(
        {
            "product_id": "csv-1",
            "title": "CSV 商品",
            "category": "食品饮料",
            "skus": json.dumps([{"sku_id": "csv-sku", "price": 10, "stock": 3}]),
        }
    )

    parsed = parse_product_file(output.getvalue().encode("utf-8"), "products.csv")
    assert parsed[0].skus[0].inventory == 3


def test_excel_import_parser_supports_flat_product():
    from services.import_parsers import parse_product_file

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["product_id", "title", "category", "base_price", "stock"])
    sheet.append(["xlsx-1", "Excel 商品", "食品饮料", 18.5, 6])
    output = io.BytesIO()
    workbook.save(output)

    parsed = parse_product_file(output.getvalue(), "products.xlsx")
    assert parsed[0].skus[0].price == 18.5
    assert parsed[0].skus[0].inventory == 6


def test_import_parser_keeps_valid_rows_and_reports_bad_and_duplicate_rows():
    from services.import_parsers import parse_product_file_result

    valid = _record()
    duplicate = {**valid, "title": "Duplicate"}
    invalid = {"product_id": "bad-1", "title": "Missing category"}

    result = parse_product_file_result(
        json.dumps([valid, invalid, duplicate], ensure_ascii=False).encode(), "products.json"
    )

    assert result.total_count == 3
    assert [record.external_id for record in result.records] == ["p-test-1"]
    assert [error["row"] for error in result.errors] == [2, 3]
    assert "required" in result.errors[0]["message"]
    assert "duplicate" in result.errors[1]["message"]


def test_authorized_api_source_adapter_is_pluggable_and_keeps_token_backend_only():
    from services.product_sources import AuthorizedApiSourceAdapter

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-token"
        return httpx.Response(200, json=[_record()])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = AuthorizedApiSourceAdapter(
        "https://catalog.example.test/products", "secret-token", client=client
    )

    result = adapter.fetch()
    assert result.total_count == 1
    assert result.records[0].external_id == "p-test-1"


def test_business_metadata_contains_truth_and_transaction_tables():
    from db.base import Base
    import db.models  # noqa: F401

    expected = {
        "products",
        "product_skus",
        "inventory",
        "product_prices",
        "vector_sync_jobs",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "order_status_events",
        "checkout_previews",
    }
    assert expected.issubset(Base.metadata.tables)


def test_synthetic_lifestyle_catalog_is_separate_and_importable():
    from services.import_parsers import parse_product_file_result

    dataset = (
        Path(__file__).resolve().parents[2]
        / "ecommerce_agent_dataset"
        / "synthetic_lifestyle_v1"
        / "products.json"
    )
    result = parse_product_file_result(dataset.read_bytes(), dataset.name)

    assert result.total_count == 42
    assert result.errors == []
    assert len(result.records) == 42
    assert {record.category for record in result.records} == {
        "首饰发饰",
        "挂件毛绒",
        "包袋收纳",
        "美妆工具",
        "文具",
        "家居日用",
        "礼赠组合",
    }
    assert all(record.attributes["data_origin"] == "synthetic" for record in result.records)


def _sqlite_catalog():
    from db.base import Base
    import db.models  # noqa: F401

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_catalog_filters_and_checkout_preview_idempotency():
    from db.models import Inventory, ProductSku
    from db.repositories.products import ProductRepository
    from schemas.commerce import CreateOrderRequest
    from schemas.imports import ProductImportRecord, ProductSkuImport
    from services.catalog_service import CatalogService
    from services.commerce_service import CommerceService
    from services.product_import_service import ProductImportService

    engine = _sqlite_catalog()
    with Session(engine) as session:
        ProductImportService(session).import_records(
            source_key="synthetic-test",
            source_name="Synthetic Test",
            source_type="test",
            filename=None,
            records=[
                ProductImportRecord(
                    external_id="gift-under-50",
                    title="可爱毛绒礼物",
                    category="挂件毛绒",
                    attributes={"data_origin": "synthetic"},
                    skus=[
                        ProductSkuImport(
                            external_id="gift-sku", price=39, inventory=2
                        )
                    ],
                ),
                ProductImportRecord(
                    external_id="bag-over-50",
                    title="通勤斜挎包",
                    category="包袋收纳",
                    attributes={"data_origin": "synthetic"},
                    skus=[
                        ProductSkuImport(
                            external_id="bag-sku", price=69, inventory=3
                        )
                    ],
                ),
            ],
        )

        catalog = CatalogService(ProductRepository(session))
        matches = catalog.list_products(
            category_id=None,
            active_only=True,
            offset=0,
            limit=20,
            query="礼物",
            max_price=50,
            in_stock=True,
            sort="price_asc",
        )
        assert [item.title for item in matches] == ["可爱毛绒礼物"]
        assert matches[0].source_key == "synthetic-test"

        sku = session.scalar(select(ProductSku).where(ProductSku.external_id == "gift-sku"))
        sku_id = sku.id
        session.commit()
        commerce = CommerceService(session)
        commerce.add_item("demo-session", sku_id, 1)
        session.rollback()
        preview = commerce.preview_checkout("demo-session")
        request = CreateOrderRequest(
            session_id="demo-session",
            confirmation_token=preview.confirmation_token,
            idempotency_key="demo-order-0001",
            recipient_name="演示用户",
            recipient_phone="13800000000",
            shipping_address="演示地址",
            payment_method="demo_alipay",
        )
        first = commerce.checkout("demo-session", request)
        session.rollback()
        repeated = commerce.checkout("demo-session", request)

        assert repeated.id == first.id
        assert first.status == "preparing"
        assert first.payment_status == "simulated_paid"
        assert [event.to_status for event in first.status_events] == [
            "created",
            "paid",
            "preparing",
        ]
        assert commerce.list_orders("demo-session", offset=0, limit=20).total == 1
        session.rollback()
        cancelled = commerce.cancel_order(first.id)
        assert cancelled.status == "cancelled"
        assert session.get(Inventory, sku_id).available_quantity == 2
    engine.dispose()


@pytest.mark.parametrize(
    ("message", "expected", "confirmed"),
    [
        ("把第二个加入购物车", "add_to_cart", False),
        ("看看我的购物车", "view_cart", False),
        ("去结算", "checkout", False),
        ("确认下单", "checkout", True),
        ("查看订单状态", "order_status", False),
        ("取消订单", "cancel_order", False),
    ],
)
def test_commerce_intents_are_deterministic(message, expected, confirmed):
    from agent.commerce_rules import commerce_understanding
    from agent.memory import ConversationState

    state = ConversationState(session_id="commerce-intent")
    state.last_order_id = "550e8400-e29b-41d4-a716-446655440000"
    understanding = commerce_understanding(message, state)

    assert understanding is not None
    assert understanding.intent.value == expected
    assert understanding.checkout_confirmed is confirmed
    if expected == "add_to_cart":
        assert understanding.target_item_index == 2
