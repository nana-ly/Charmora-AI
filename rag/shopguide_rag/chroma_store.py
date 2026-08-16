from __future__ import annotations

from pathlib import Path
from typing import Any

from shopguide_rag.catalog import (
    build_product_document,
    load_product_map,
    load_products,
    product_metadata,
)
from shopguide_rag.embedding_service import EmbeddingService


class ProductVectorStore:
    def __init__(
        self,
        persist_dir: Path,
        collection_name: str = "products",
        embedding_base_url: str | None = None,
        embedding_api_key: str | None = None,
        embedding_model: str = "text-embedding-v4",
        embedding_dimensions: int | None = None,
    ) -> None:
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_base_url = embedding_base_url
        self.embedding_api_key = embedding_api_key
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.embedding_service = EmbeddingService(
            base_url=self.embedding_base_url,
            api_key=self.embedding_api_key,
            model=self.embedding_model,
            dimensions=self.embedding_dimensions,
        )

    def _get_collection(self) -> Any:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("Missing dependency `chromadb`. Install dependencies in rag/.") from exc

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_dir))
        return client.get_or_create_collection(name=self.collection_name, metadata={"hnsw:space": "cosine"})

    def index_dataset(self, dataset_root: Path) -> int:
        products = load_products(dataset_root)
        collection = self._get_collection()
        documents = [build_product_document(product) for product in products]
        embeddings = self.embedding_service.embed_batch(documents)

        collection.upsert(
            ids=[product.product_id for product in products],
            embeddings=embeddings,
            documents=documents,
            metadatas=[product_metadata(product) for product in products],
        )
        return len(products)

    def query_by_text(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        collection = self._get_collection()
        query_embedding = self.embedding_service.embed(query)
        result = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        return _normalize_query_result(result)

    def query_by_embedding(self, embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        result = self._get_collection().query(
            query_embeddings=[embedding],
            n_results=top_k,
        )
        return _normalize_query_result(result)

    def query_by_product_id(
        self, dataset_root: Path, product_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        product_map = load_product_map(dataset_root)
        if product_id not in product_map:
            raise ValueError(f"Unknown product_id: {product_id}")

        query_text = build_product_document(product_map[product_id])
        candidates = self.query_by_text(query_text, top_k=top_k + 1)
        return [item for item in candidates if item["product_id"] != product_id][:top_k]

    def upsert_product(
        self,
        *,
        product_id: str,
        document: str,
        metadata: dict[str, Any],
    ) -> None:
        """Incrementally index one product without storing price or inventory facts."""
        collection = self._get_collection()
        collection.upsert(
            ids=[product_id],
            embeddings=[self.embedding_service.embed(document)],
            documents=[document],
            metadatas=[metadata],
        )

    def delete_products(self, product_ids: list[str]) -> None:
        if product_ids:
            self._get_collection().delete(ids=product_ids)


def _normalize_query_result(result: dict[str, list[list[Any]]]) -> list[dict[str, Any]]:
    ids = result.get("ids", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    documents = result.get("documents", [[]])[0]
    distances = result.get("distances", [[]])[0]

    rows: list[dict[str, Any]] = []
    for index, product_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        rows.append(
            {
                "product_id": product_id,
                "score": 1 - distances[index] if index < len(distances) else None,
                "document": documents[index] if index < len(documents) else None,
                "metadata": metadata,
            }
        )
    return rows
