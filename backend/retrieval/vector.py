"""向量检索适配器。

该模块把独立的 ``rag/shopguide_rag`` ChromaDB 检索脚本包装成后端统一的
Retriever 接口，让推荐链路可以在关键词检索和向量检索之间切换。
"""

import sys
from pathlib import Path
from typing import Any

from recommendation_core.data import products
from retrieval.base import RetrievalResult, Retriever


class VectorRetriever(Retriever):
    """基于 ChromaDB 商品向量索引的检索器。"""

    def __init__(
        self,
        store: Any | None = None,
        persist_dir: Path | None = None,
        embedding_base_url: str | None = None,
        embedding_api_key: str | None = None,
        collection_name: str = "products",
        embedding_model: str = "text-embedding-v4",
        embedding_dimensions: int = 1024,
    ) -> None:
        self.store = store or _create_product_vector_store(
            persist_dir=persist_dir,
            embedding_base_url=embedding_base_url,
            embedding_api_key=embedding_api_key,
            collection_name=collection_name,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
        )

    def search(
        self,
        query: str,
        candidates: list[dict[str, Any]] | None = None,
        top_k: int = 3,
    ) -> list[RetrievalResult]:
        """根据用户需求执行向量召回，并返回后端统一检索结果。"""
        if candidates == []:
            return []

        source = products if candidates is None else candidates
        product_by_id = {
            str(product.get("product_id")): product
            for product in source
            if product.get("product_id")
        }
        query_limit = max(top_k, len(product_by_id) if candidates is not None else top_k)
        raw_results = self.store.query_by_text(query, top_k=query_limit)

        results: list[RetrievalResult] = []
        for row in raw_results:
            product_id = str(row.get("product_id", ""))
            if product_by_id and product_id not in product_by_id:
                continue

            product = product_by_id.get(product_id) or _metadata_to_product(row)
            results.append(
                RetrievalResult(
                    product=product,
                    evidence=_build_evidence(row),
                    score=float(row.get("score") or 0.0),
                )
            )
            if len(results) >= top_k:
                break

        return results


def _create_product_vector_store(
    persist_dir: Path | None,
    embedding_base_url: str | None,
    embedding_api_key: str | None,
    collection_name: str,
    embedding_model: str,
    embedding_dimensions: int,
) -> Any:
    repo_root = Path(__file__).resolve().parents[2]
    rag_package_root = repo_root / "rag"
    if str(rag_package_root) not in sys.path:
        sys.path.append(str(rag_package_root))

    from shopguide_rag.chroma_store import ProductVectorStore

    return ProductVectorStore(
        persist_dir=persist_dir or repo_root / "rag" / ".chroma" / "products",
        collection_name=collection_name,
        embedding_base_url=embedding_base_url,
        embedding_api_key=embedding_api_key,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
    )


def _metadata_to_product(row: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {})
    if "base_price" not in metadata and "price_min" in metadata:
        metadata["base_price"] = metadata["price_min"]
    if "image_path" not in metadata:
        metadata["image_path"] = ""
    metadata.setdefault("product_id", row.get("product_id", ""))
    return metadata


def _build_evidence(row: dict[str, Any]) -> str:
    score = float(row.get("score") or 0.0)
    document = " ".join(str(row.get("document") or "").split())
    if len(document) > 120:
        document = f"{document[:120]}..."
    if document:
        return f"向量召回：相似度 {score:.2f}；{document}"
    return f"向量召回：相似度 {score:.2f}。"

