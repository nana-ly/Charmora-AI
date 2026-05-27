import pytest

from core.config import AppConfig, RAGConfig
from retrieval.base import RetrievalResult
from retrieval.keyword import KeywordRetriever
from services import retriever_factory


class FakeVectorRetriever:
    def search(self, query: str, candidates=None, top_k: int = 3):
        return [
            RetrievalResult(
                product={
                    "product_id": "p_vector",
                    "title": "向量商品",
                    "brand": "测试品牌",
                    "category": "数码电子",
                    "base_price": 100,
                },
                evidence=f"向量召回：{query}",
                score=0.9,
            )
        ][:top_k]


class FailingVectorRetriever:
    def search(self, query: str, candidates=None, top_k: int = 3):
        raise RuntimeError("vector failed")


def test_create_vector_retriever_passes_rag_config(monkeypatch):
    captured = {}

    class FakeVectorRetrieverClass:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        retriever_factory,
        "VectorRetriever",
        FakeVectorRetrieverClass,
    )

    retriever_factory.create_vector_retriever(
        AppConfig(
            rag=RAGConfig(
                embedding_url="https://embedding.example.test/v1",
                embedding_api="test-key",
                embedding_model="test-embedding",
                embedding_dimensions=512,
            )
        )
    )

    assert captured == {
        "embedding_base_url": "https://embedding.example.test/v1",
        "embedding_api_key": "test-key",
        "embedding_model": "test-embedding",
        "embedding_dimensions": 512,
    }


def test_select_retriever_returns_keyword_retriever():
    retriever = retriever_factory.select_retriever(AppConfig(retriever_mode="keyword"))

    assert isinstance(retriever, KeywordRetriever)


def test_select_retriever_returns_vector_retriever(monkeypatch):
    class FakeVectorRetriever:
        pass

    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        lambda config=None: FakeVectorRetriever(),
    )

    retriever = retriever_factory.select_retriever(AppConfig(retriever_mode="vector"))

    assert isinstance(retriever, FakeVectorRetriever)


def test_select_retrieve_func_returns_vector_adapter(monkeypatch):
    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        lambda config=None: FakeVectorRetriever(),
    )

    retrieve_func = retriever_factory.select_retrieve_func(
        AppConfig(retriever_mode="vector")
    )

    assert retrieve_func is not None
    results = retrieve_func("拍照手机", candidates=None, top_k=1)
    assert results[0]["product"]["product_id"] == "p_vector"
    assert results[0]["evidence"].startswith("向量召回")


def test_select_retrieve_func_returns_none_for_keyword_mode():
    retrieve_func = retriever_factory.select_retrieve_func(
        AppConfig(retriever_mode="keyword")
    )

    assert retrieve_func is None


def test_select_retrieve_func_rejects_unknown_mode():
    with pytest.raises(ValueError, match="RETRIEVER_MODE"):
        retriever_factory.select_retrieve_func(AppConfig(retriever_mode="vectro"))


def test_select_retrieve_func_propagates_vector_creation_error(monkeypatch):
    def fail_create_vector_retriever(config=None):
        raise RuntimeError("missing embedding config")

    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        fail_create_vector_retriever,
    )

    with pytest.raises(RuntimeError, match="missing embedding config"):
        retriever_factory.select_retrieve_func(AppConfig(retriever_mode="vector"))


def test_vector_adapter_propagates_search_error():
    retrieve_func = retriever_factory.legacy_retrieve_from_retriever(
        FailingVectorRetriever()
    )

    with pytest.raises(RuntimeError, match="vector failed"):
        retrieve_func("想买拍照手机", candidates=None, top_k=1)
