import pytest

from core.config import AppConfig
from services import recommendation_service


def test_run_recommendation_uses_config_default_top_k_when_not_supplied(monkeypatch):
    calls = {}

    def fake_select_retrieve_func(config=None):
        return None

    def fake_recommend_products(query: str, top_k: int = 3, retrieve_func=None):
        calls["query"] = query
        calls["top_k"] = top_k
        calls["retrieve_func"] = retrieve_func
        return {"query": query, "filters": {}, "items": []}

    monkeypatch.setattr(
        recommendation_service,
        "select_retrieve_func",
        fake_select_retrieve_func,
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
        "retrieve_func": None,
    }


def test_run_recommendation_allows_explicit_top_k(monkeypatch):
    calls = {}

    def fake_recommend_products(query: str, top_k: int = 3, retrieve_func=None):
        calls["top_k"] = top_k
        return {"query": query, "filters": {}, "items": []}

    monkeypatch.setattr(
        recommendation_service,
        "select_retrieve_func",
        lambda config=None: None,
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


def test_run_recommendation_passes_selected_retrieve_func(monkeypatch):
    calls = {}

    def fake_retrieve_func(query: str, candidates=None, top_k: int = 3):
        return []

    def fake_recommend_products(query: str, top_k: int = 3, retrieve_func=None):
        calls["query"] = query
        calls["top_k"] = top_k
        calls["retrieve_func"] = retrieve_func
        return {"query": query, "filters": {}, "items": []}

    monkeypatch.setattr(
        recommendation_service,
        "select_retrieve_func",
        lambda config=None: fake_retrieve_func,
    )
    monkeypatch.setattr(
        recommendation_service,
        "recommend_products",
        fake_recommend_products,
    )

    recommendation_service.run_recommendation("拍照手机", top_k=5)

    assert calls["query"] == "拍照手机"
    assert calls["top_k"] == 5
    assert calls["retrieve_func"] is fake_retrieve_func


def test_run_recommendation_propagates_pipeline_errors(monkeypatch):
    def fake_recommend_products(query: str, top_k: int = 3, retrieve_func=None):
        raise RuntimeError("pipeline failed")

    monkeypatch.setattr(
        recommendation_service,
        "select_retrieve_func",
        lambda config=None: None,
    )
    monkeypatch.setattr(
        recommendation_service,
        "recommend_products",
        fake_recommend_products,
    )

    with pytest.raises(RuntimeError, match="pipeline failed"):
        recommendation_service.run_recommendation("拍照手机", top_k=2)
