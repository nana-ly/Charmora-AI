import pytest

from core.config import AppConfig
from services import recommendation_service


def test_run_recommendation_uses_config_default_top_k_when_not_supplied(monkeypatch):
    selected_retriever = object()
    calls = {}

    def fake_recommend_products(query: str, top_k: int = 3, retriever=None):
        calls["query"] = query
        calls["top_k"] = top_k
        calls["retriever"] = retriever
        return {"query": query, "filters": {}, "items": []}

    monkeypatch.setattr(
        recommendation_service,
        "select_retriever",
        lambda config=None: selected_retriever,
    )
    monkeypatch.setattr(
        recommendation_service,
        "recommend_products",
        fake_recommend_products,
    )
    monkeypatch.setattr(
        recommendation_service,
        "load_app_config",
        lambda: AppConfig(default_top_k=4),
    )

    response = recommendation_service.run_recommendation("拍照手机")

    assert response == {"query": "拍照手机", "filters": {}, "items": []}
    assert calls == {
        "query": "拍照手机",
        "top_k": 4,
        "retriever": selected_retriever,
    }


def test_run_recommendation_allows_explicit_top_k(monkeypatch):
    calls = {}

    def fake_recommend_products(query: str, top_k: int = 3, retriever=None):
        calls["top_k"] = top_k
        return {"query": query, "filters": {}, "items": []}

    monkeypatch.setattr(
        recommendation_service,
        "select_retriever",
        lambda config=None: object(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "recommend_products",
        fake_recommend_products,
    )
    monkeypatch.setattr(
        recommendation_service,
        "load_app_config",
        lambda: AppConfig(default_top_k=4),
    )

    recommendation_service.run_recommendation("拍照手机", top_k=2)

    assert calls["top_k"] == 2


def test_run_recommendation_passes_selected_retriever(monkeypatch):
    selected_retriever = object()
    calls = {}

    def fake_recommend_products(query: str, top_k: int = 3, retriever=None):
        calls["query"] = query
        calls["top_k"] = top_k
        calls["retriever"] = retriever
        return {"query": query, "filters": {}, "items": []}

    monkeypatch.setattr(
        recommendation_service,
        "select_retriever",
        lambda config=None: selected_retriever,
    )
    monkeypatch.setattr(
        recommendation_service,
        "recommend_products",
        fake_recommend_products,
    )

    recommendation_service.run_recommendation("拍照手机", top_k=5)

    assert calls["query"] == "拍照手机"
    assert calls["top_k"] == 5
    assert calls["retriever"] is selected_retriever


def test_run_recommendation_propagates_pipeline_errors(monkeypatch):
    def fake_recommend_products(query: str, top_k: int = 3, retriever=None):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(
        recommendation_service,
        "select_retriever",
        lambda config=None: object(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "recommend_products",
        fake_recommend_products,
    )

    with pytest.raises(RuntimeError, match="pipeline failed"):
        recommendation_service.run_recommendation("拍照手机", top_k=2)
