import pytest

from core.config import AppConfig
from services import recommendation_service


@pytest.fixture(autouse=True)
def reset_global_recommendation_service():
    recommendation_service.reset_recommendation_service_for_tests()
    yield
    recommendation_service.reset_recommendation_service_for_tests()


class DummyReasonService:
    def generate(self, query, product, evidence, fallback_reason=None):
        return fallback_reason or evidence


def test_recommendation_service_caches_retriever_and_reason_service():
    retriever = object()
    reason_service = DummyReasonService()
    calls = {
        "retriever_factory": 0,
        "reason_service_factory": 0,
        "recommend": [],
    }

    def retriever_factory(config):
        calls["retriever_factory"] += 1
        assert config.default_top_k == 4
        return retriever

    def reason_service_factory():
        calls["reason_service_factory"] += 1
        return reason_service

    def recommend_func(query, **kwargs):
        calls["recommend"].append((query, kwargs))
        return {"query": query, "filters": {}, "items": []}

    service = recommendation_service.RecommendationService(
        config=AppConfig(default_top_k=4),
        retriever_factory=retriever_factory,
        reason_service_factory=reason_service_factory,
        recommend_func=recommend_func,
    )

    service.recommend("camera phone")
    service.recommend("battery phone", top_k=2)

    assert calls["retriever_factory"] == 1
    assert calls["reason_service_factory"] == 1
    assert calls["recommend"] == [
        (
            "camera phone",
            {
                "top_k": 4,
                "retriever": retriever,
                "reason_service": reason_service,
            },
        ),
        (
            "battery phone",
            {
                "top_k": 2,
                "retriever": retriever,
                "reason_service": reason_service,
            },
        ),
    ]


def test_recommendation_service_passes_negative_filters_to_pipeline():
    captured = {}
    negative_filters = object()

    def recommend_func(query, **kwargs):
        captured.update(kwargs)
        return {"query": query, "filters": {}, "items": []}

    service = recommendation_service.RecommendationService(
        config=AppConfig(default_top_k=3),
        retriever_factory=lambda config: object(),
        reason_service_factory=DummyReasonService,
        recommend_func=recommend_func,
    )

    service.recommend("phone without apple", negative_filters=negative_filters)

    assert captured["negative_filters"] is negative_filters


def test_recommendation_service_ready_reports_retriever_failure():
    def failing_retriever_factory(config):
        raise RuntimeError("missing embedding config")

    service = recommendation_service.RecommendationService(
        config=AppConfig(retriever_mode="vector"),
        retriever_factory=failing_retriever_factory,
        reason_service_factory=DummyReasonService,
        recommend_func=lambda query, **kwargs: {"items": []},
    )

    assert service.ready() == {
        "status": "not_ready",
        "retriever_mode": "vector",
        "error": "missing embedding config",
    }


def test_reset_recommendation_service_for_tests_creates_fresh_global_service(monkeypatch):
    retrievers = [object(), object()]
    calls = {"retriever_factory": 0}

    def retriever_factory(config):
        calls["retriever_factory"] += 1
        return retrievers.pop(0)

    monkeypatch.setattr(
        recommendation_service,
        "select_retriever",
        retriever_factory,
    )
    monkeypatch.setattr(
        recommendation_service,
        "load_app_config",
        lambda: AppConfig(default_top_k=3),
    )
    monkeypatch.setattr(
        recommendation_service,
        "create_default_reason_service",
        DummyReasonService,
    )
    monkeypatch.setattr(
        recommendation_service,
        "recommend_products",
        lambda query, **kwargs: {
            "retriever_id": id(kwargs["retriever"]),
            "items": [],
        },
    )

    recommendation_service.reset_recommendation_service_for_tests()
    first = recommendation_service.run_recommendation("camera phone")
    recommendation_service.reset_recommendation_service_for_tests()
    second = recommendation_service.run_recommendation("camera phone")

    assert calls["retriever_factory"] == 2
    assert first["retriever_id"] != second["retriever_id"]


def test_run_recommendation_uses_config_default_top_k_when_not_supplied(monkeypatch):
    selected_retriever = object()
    selected_reason_service = DummyReasonService()
    calls = {}

    def fake_recommend_products(
        query: str,
        top_k: int = 3,
        retriever=None,
        reason_service=None,
    ):
        calls["query"] = query
        calls["top_k"] = top_k
        calls["retriever"] = retriever
        calls["reason_service"] = reason_service
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
    monkeypatch.setattr(
        recommendation_service,
        "create_default_reason_service",
        lambda: selected_reason_service,
    )

    response = recommendation_service.run_recommendation("camera phone")

    assert response == {"query": "camera phone", "filters": {}, "items": []}
    assert calls == {
        "query": "camera phone",
        "top_k": 4,
        "retriever": selected_retriever,
        "reason_service": selected_reason_service,
    }


def test_run_recommendation_allows_explicit_top_k(monkeypatch):
    calls = {}

    def fake_recommend_products(
        query: str,
        top_k: int = 3,
        retriever=None,
        reason_service=None,
    ):
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
    monkeypatch.setattr(
        recommendation_service,
        "create_default_reason_service",
        DummyReasonService,
    )

    recommendation_service.run_recommendation("camera phone", top_k=2)

    assert calls["top_k"] == 2


def test_run_recommendation_passes_selected_retriever(monkeypatch):
    selected_retriever = object()
    calls = {}

    def fake_recommend_products(
        query: str,
        top_k: int = 3,
        retriever=None,
        reason_service=None,
    ):
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
        "create_default_reason_service",
        DummyReasonService,
    )

    recommendation_service.run_recommendation("camera phone", top_k=5)

    assert calls["query"] == "camera phone"
    assert calls["top_k"] == 5
    assert calls["retriever"] is selected_retriever


def test_run_recommendation_propagates_pipeline_errors(monkeypatch):
    def fake_recommend_products(
        query: str,
        top_k: int = 3,
        retriever=None,
        reason_service=None,
    ):
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
    monkeypatch.setattr(
        recommendation_service,
        "create_default_reason_service",
        DummyReasonService,
    )

    with pytest.raises(RuntimeError, match="pipeline failed"):
        recommendation_service.run_recommendation("camera phone", top_k=2)
