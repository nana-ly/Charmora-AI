from __future__ import annotations

import argparse
import json
from pathlib import Path

from shopguide_rag.chroma_store import ProductVectorStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index and query product data with ChromaDB.")
    parser.add_argument(
        "--dataset-root",
        default="../ecommerce_agent_dataset",
        help="Path to the product dataset root.",
    )
    parser.add_argument(
        "--persist-dir",
        default=".chroma/products",
        help="Path to the ChromaDB persistence directory.",
    )
    parser.add_argument(
        "--collection-name",
        default="products",
        help="Chroma collection name.",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-v4",
        help="Embedding model name for the compatible embeddings API.",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=1024,
        help="Optional embedding dimensions passed to the embeddings API.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("index", help="Build or refresh the product vector index.")

    query_parser = subparsers.add_parser("query", help="Run similarity search.")
    query_group = query_parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", help="Free-text query.")
    query_group.add_argument("--product-id", help="Query with an existing product ID.")
    query_parser.add_argument("--top-k", type=int, default=5, help="Number of results.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    store = ProductVectorStore(
        persist_dir=Path(args.persist_dir),
        collection_name=args.collection_name,
        embedding_model=args.embedding_model,
        embedding_dimensions=args.embedding_dimensions,
    )
    dataset_root = Path(args.dataset_root)

    if args.command == "index":
        indexed_count = store.index_dataset(dataset_root)
        print(f"Indexed {indexed_count} products into {args.persist_dir}")
        return

    if args.query:
        results = store.query_by_text(query=args.query, top_k=args.top_k)
    else:
        results = store.query_by_product_id(
            dataset_root=dataset_root,
            product_id=args.product_id,
            top_k=args.top_k,
        )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
