from pathlib import Path

from shopguide_rag import chroma_store
from shopguide_rag.catalog import build_product_document, load_products, product_metadata


def test_load_products_reads_dataset_records():
    dataset_root = Path("../ecommerce_agent_dataset")

    products = load_products(dataset_root)

    assert len(products) == 100
    assert products[0].product_id.startswith("p_")


def test_build_product_document_contains_retrieval_fields():
    dataset_root = Path("../ecommerce_agent_dataset")
    product = load_products(dataset_root)[0]

    document = build_product_document(product)

    assert product.title in document
    assert product.brand in document
    assert "营销描述" in document
    assert "FAQ摘要" in document


def test_product_metadata_contains_filterable_fields():
    dataset_root = Path("../ecommerce_agent_dataset")
    product = load_products(dataset_root)[0]

    metadata = product_metadata(product)

    assert metadata["product_id"] == product.product_id
    assert metadata["category_path"] == f"{product.category}/{product.sub_category}"
    assert metadata["price_min"] <= metadata["price_max"]
    assert "sku_count" in metadata
    assert "faq_count" in metadata
    assert "review_count" in metadata


def test_product_vector_store_passes_embedding_configuration(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class FakeEmbeddingService:
        def __init__(
            self,
            base_url=None,
            api_key=None,
            model=None,
            dimensions=None,
        ):
            captured["base_url"] = base_url
            captured["api_key"] = api_key
            captured["model"] = model
            captured["dimensions"] = dimensions

    monkeypatch.setattr(chroma_store, "EmbeddingService", FakeEmbeddingService)

    store = chroma_store.ProductVectorStore(
        persist_dir=tmp_path,
        embedding_base_url="https://embedding.example.test/v1",
        embedding_api_key="test-key",
        embedding_model="test-embedding",
        embedding_dimensions=512,
    )

    assert store.embedding_base_url == "https://embedding.example.test/v1"
    assert store.embedding_api_key == "test-key"
    assert captured == {
        "base_url": "https://embedding.example.test/v1",
        "api_key": "test-key",
        "model": "test-embedding",
        "dimensions": 512,
    }
