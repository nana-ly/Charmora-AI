import pytest
from fastapi.testclient import TestClient

import api.deps as api_deps
import api.rag as api_rag
import api.recommend as api_recommend
import services.retriever_factory as retriever_factory
from agent.memory import InMemoryConversationStore, PurchaseContext
from agent.runner import create_agent_runner
from agent.tools import RecommendationTool
from agent.understanding import UserIntent, UserUnderstanding
from core.config import AppConfig
from main import app
from schemas.chat import ChatResponse
from schemas.product import ProductCard
from services.recommendation_service import run_recommendation


client = TestClient(app)


class FakeVectorRetriever:
    def search(self, query: str, candidates=None, top_k: int = 3):
        from retrieval.base import RetrievalResult

        product = {
            "product_id": "p_rag_1",
            "title": "RAG 拍照旗舰手机",
            "brand": "Apple",
            "category": "数码电子",
            "base_price": 8999,
        }
        return [
            RetrievalResult(
                product=product,
                evidence=f"向量召回：匹配“{query}”。",
                score=0.91,
            )
        ][:top_k]


class FailingVectorSearchRetriever:
    def search(self, query: str, candidates=None, top_k: int = 3):
        raise RuntimeError("embedding api failed")


class FakeUnderstandingService:
    def __init__(self, understanding: UserUnderstanding | None = None):
        self.understanding = understanding

    def understand(self, *, message, conversation):
        if self.understanding is not None:
            return self.understanding

        return UserUnderstanding(
            intent=UserIntent.RECOMMEND,
            confidence=0.9,
            purchase_need=message,
            preference_updates={
                "category": "数码电子",
                "budget": "9000以内",
                "focus": ["拍照"],
            },
        )


def inject_recommend_chat_runner(
    monkeypatch,
    *,
    recommendation_tool=None,
    understanding_service=None,
):
    monkeypatch.setattr(
        api_deps,
        "agent_runner",
        create_agent_runner(
            config=AppConfig(agent_runner="langgraph"),
            recommendation_tool=recommendation_tool
            or RecommendationTool(recommend_func=run_recommendation),
            understanding_service=understanding_service or FakeUnderstandingService(),
        ),
    )


def test_root_returns_service_metadata():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "ShopGuide RAG API",
        "status": "running",
    }


def test_health_returns_ok_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recommend_returns_three_product_cards_from_loaded_products(monkeypatch):
    monkeypatch.setenv("RETRIEVER_MODE", "keyword")
    response = client.post(
        "/recommend",
        json={"query": "预算9000以内，想买拍照和剪视频好的手机"},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["query"] == "预算9000以内，想买拍照和剪视频好的手机"
    assert payload["filters"] == {
        "category": "数码电子",
        "max_price": 9000,
        "brand": None,
        "keywords": ["手机", "拍照", "剪视频"],
    }

    items = payload["items"]
    assert len(items) == 3

    required_fields = {
        "product_id",
        "title",
        "brand",
        "price",
        "reason",
        "evidence",
    }
    for item in items:
        assert required_fields <= item.keys()

    assert items[0]["product_id"].startswith("p_digital_")
    assert items[0]["reason"]
    assert items[0]["evidence"].startswith("临时匹配")


def test_rag_search_returns_vector_retrieval_debug_results(monkeypatch):
    monkeypatch.setattr(api_rag, "create_vector_retriever", lambda: FakeVectorRetriever())
    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        lambda config=None: FakeVectorRetriever(),
    )

    response = client.post(
        "/rag/search",
        json={"query": "预算9000以内，想买拍照好的手机", "top_k": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "预算9000以内，想买拍照好的手机"
    assert payload["items"] == [
        {
            "product_id": "p_rag_1",
            "title": "RAG 拍照旗舰手机",
            "brand": "Apple",
            "score": 0.91,
            "evidence": "向量召回：匹配“预算9000以内，想买拍照好的手机”。",
        }
    ]


def test_recommend_uses_vector_retriever_by_default(monkeypatch):
    monkeypatch.setenv("RETRIEVER_MODE", "vector")
    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        lambda config=None: FakeVectorRetriever(),
    )

    response = client.post(
        "/recommend",
        json={"query": "预算9000以内，想买拍照好的手机"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["product_id"] == "p_rag_1"
    assert payload["items"][0]["evidence"].startswith("向量召回")


def test_recommend_returns_500_when_vector_retriever_fails(monkeypatch):
    def fail_create_vector_retriever(config=None):
        raise RuntimeError("missing embedding config")

    monkeypatch.setenv("RETRIEVER_MODE", "vector")
    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        fail_create_vector_retriever,
    )

    with pytest.raises(RuntimeError, match="missing embedding config"):
        client.post(
            "/recommend",
            json={"query": "预算9000以内，想买拍照好的手机"},
        )


def test_recommend_returns_500_when_vector_search_fails(monkeypatch):
    monkeypatch.setenv("RETRIEVER_MODE", "vector")
    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        lambda config=None: FailingVectorSearchRetriever(),
    )

    with pytest.raises(RuntimeError, match="embedding api failed"):
        client.post(
            "/recommend",
            json={"query": "预算9000以内，想买拍照好的手机"},
        )


def test_recommend_route_returns_200_with_empty_items_for_no_results(monkeypatch):
    route = next(route for route in app.routes if route.path == "/recommend")
    assert route.response_model is None

    fake_result = {
        "query": "100 元以内的手机",
        "filters": {
            "category": "数码电子",
            "max_price": 100,
            "brand": None,
            "keywords": ["手机"],
        },
        "items": [],
    }

    monkeypatch.setattr(
        api_recommend,
        "run_recommendation",
        lambda query: fake_result,
    )

    response = client.post("/recommend", json={"query": "100 元以内的手机"})

    assert response.status_code == 200
    assert response.json() == fake_result


def test_chat_uses_vector_retriever_by_default(monkeypatch):
    monkeypatch.setenv("RETRIEVER_MODE", "vector")
    monkeypatch.setattr(
        retriever_factory,
        "create_vector_retriever",
        lambda config=None: FakeVectorRetriever(),
    )
    inject_recommend_chat_runner(monkeypatch)

    response = client.post(
        "/chat",
        json={
            "session_id": "test-chat-vector-session",
            "message": "预算9000以内的拍照手机",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["product_id"] == "p_rag_1"
    assert payload["items"][0]["evidence"].startswith("向量召回")


def test_recommend_supports_budget_without_suffix():
    response = client.post(
        "/recommend",
        json={"query": "预算9000想买续航好的学生手机"},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["filters"]["category"] == "数码电子"
    assert payload["filters"]["max_price"] == 9000
    assert "续航" in payload["filters"]["keywords"]
    assert "学生" in payload["filters"]["keywords"]
    assert len(payload["items"]) == 3


def test_chat_returns_agent_response_and_state(monkeypatch):
    inject_recommend_chat_runner(monkeypatch)

    response = client.post(
        "/chat",
        json={
            "session_id": "test-chat-session",
            "message": "预算9000以内的拍照手机",
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["session_id"] == "test-chat-session"
    assert payload["reply"]
    assert payload["state"]["intent"] == "recommend"
    assert payload["state"]["preferences"]["category"] == "数码电子"
    assert len(payload["items"]) == 3


def test_chat_keeps_response_contract_with_langgraph_runner(monkeypatch):
    inject_recommend_chat_runner(
        monkeypatch,
        recommendation_tool=RecommendationTool(
            recommend_func=run_recommendation,
        ),
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "test-chat-langgraph-session",
            "message": "预算9000以内的拍照手机",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"session_id", "reply", "items", "state"}
    assert payload["session_id"] == "test-chat-langgraph-session"
    assert payload["state"]["intent"] == "recommend"
    assert len(payload["items"]) == 3
    assert {
        "product_id",
        "title",
        "brand",
        "price",
        "reason",
        "evidence",
    } <= payload["items"][0].keys()


def test_chat_response_exposes_canonical_target_key(monkeypatch):
    inject_recommend_chat_runner(
        monkeypatch,
        understanding_service=FakeUnderstandingService(
            UserUnderstanding(
                intent=UserIntent.RECOMMEND,
                confidence=0.9,
                purchase_need="推荐手机",
                preference_updates={
                    "target_category": "手机",
                    "category": "数码电子",
                    "canonical_target_key": "phone",
                    "is_broad_category_request": True,
                },
            )
        ),
    )

    response = client.post(
        "/chat",
        json={"session_id": "api-canonical", "message": "推荐手机"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"]["preferences"]["canonical_target_key"] == "phone"
    assert body["state"]["preferences"]["is_broad_category_request"] is True


def test_chat_no_results_keeps_response_shape_and_relax_options(monkeypatch):
    def no_results_recommendation(query, top_k=3, negative_filters=None):
        return {
            "query": query,
            "filters": {
                "category": "数码电子",
                "max_price": 100,
                "brand": None,
                "keywords": ["手机"],
            },
            "items": [],
        }

    inject_recommend_chat_runner(
        monkeypatch,
        recommendation_tool=RecommendationTool(
            recommend_func=no_results_recommendation
        ),
        understanding_service=FakeUnderstandingService(
            UserUnderstanding(
                intent=UserIntent.RECOMMEND,
                confidence=0.9,
                purchase_need="100 元以内的手机",
                preference_updates={
                    "target_category": "手机",
                    "category": "数码电子",
                    "canonical_target_key": "phone",
                    "max_price": 100,
                },
            )
        ),
    )

    response = client.post(
        "/chat",
        json={"session_id": "api-no-results-session", "message": "推荐手机"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"session_id", "reply", "items", "state"}
    assert body["items"] == []
    assert body["state"]["result_status"] == "no_results"
    assert body["state"]["latest_attempt_status"] == "no_results"
    assert body["state"]["relax_options"]
    assert "tool_error" not in body["state"]


def test_chat_response_includes_negative_feedback_state(monkeypatch):
    store = InMemoryConversationStore()
    apple_item = ProductCard(
        product_id="p_apple_1",
        title="iPhone 15",
        brand="苹果",
        price=5999,
        reason="上一轮推荐",
        evidence="seed",
    )
    state = store.get_or_create("api-negative-session")
    state.purchase_need = "想买一台拍照好的手机"
    state.preferences = {
        "target_category": "数码电子",
        "category": "数码电子",
        "focus": ["拍照"],
    }
    state.last_successful_items = [apple_item]
    state.last_items = [apple_item]

    captured = {}

    def capture_recommendation(query, top_k=3, negative_filters=None):
        captured["negative_filters"] = negative_filters
        return {
            "query": query,
            "filters": {
                "category": "数码电子",
                "max_price": None,
                "brand": None,
                "keywords": ["拍照"],
            },
            "items": [
                ProductCard(
                    product_id="p_huawei_1",
                    title="华为 Mate 60",
                    brand="华为",
                    price=6999,
                    reason="避开苹果后的推荐",
                    evidence="test",
                )
            ],
        }

    monkeypatch.setattr(
        api_deps,
        "agent_runner",
        create_agent_runner(
            config=AppConfig(agent_runner="langgraph"),
            store=store,
            recommendation_tool=RecommendationTool(
                recommend_func=capture_recommendation
            ),
            understanding_service=FakeUnderstandingService(
                UserUnderstanding(
                    intent=UserIntent.UPDATE_PREFERENCE,
                    confidence=0.9,
                    negative_updates={"excluded_brands": ["苹果"]},
                )
            ),
        ),
    )

    response = client.post(
        "/chat",
        json={"session_id": "api-negative-session", "message": "不要苹果"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"]["negative_feedback"]["applied"] is True
    assert body["state"]["excluded_brands"] == ["苹果"]
    assert captured["negative_filters"].excluded_brands == ["苹果"]


def test_chat_negative_feedback_noop_keeps_response_contract(monkeypatch):
    store = InMemoryConversationStore()
    state = store.get_or_create("api-negative-noop-session")
    state.purchase_need = "拍照好的手机"
    state.preferences = {
        "target_category": "手机",
        "category": "数码电子",
        "canonical_target_key": "phone",
    }
    state.excluded_brands = ["苹果"]
    store.save(state)

    def fail_recommendation(query, top_k=3, negative_filters=None):
        raise AssertionError("noop negative feedback should not call recommendation")

    monkeypatch.setattr(
        api_deps,
        "agent_runner",
        create_agent_runner(
            config=AppConfig(agent_runner="langgraph"),
            store=store,
            recommendation_tool=RecommendationTool(
                recommend_func=fail_recommendation
            ),
            understanding_service=FakeUnderstandingService(
                UserUnderstanding(
                    intent=UserIntent.UPDATE_PREFERENCE,
                    confidence=0.9,
                    negative_updates={"excluded_brands": ["苹果"]},
                )
            ),
        ),
    )

    response = client.post(
        "/chat",
        json={"session_id": "api-negative-noop-session", "message": "不要苹果"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"session_id", "reply", "items", "state"}
    assert body["items"] == []
    assert body["state"]["action"] == "reply_only"
    assert body["state"]["negative_feedback"]["noop"] is True
    assert body["state"]["negative_feedback"]["noop_reason"] == "already_excluded"
    assert body["state"]["excluded_brands"] == ["苹果"]


def test_chat_pending_restore_confirmation_keeps_response_contract(monkeypatch):
    store = InMemoryConversationStore()
    phone_item = ProductCard(
        product_id="p_restore_phone",
        title="恢复的拍照手机",
        brand="TestPhone",
        price=2999,
        reason="符合之前的手机需求",
        evidence="restore",
    )
    skin_item = ProductCard(
        product_id="p_restore_skin",
        title="当前护肤品",
        brand="TestSkin",
        price=199,
        reason="当前护肤品结果",
        evidence="skin",
    )
    state = store.get_or_create("api-restore-confirm-session")
    state.purchase_need = "适合干皮的护肤品"
    state.preferences = {
        "target_category": "护肤品",
        "category": "美妆护肤",
        "canonical_target_key": "skin_care",
    }
    state.pending_restore_category = "phone"
    state.pending_restore_display_target = "手机"
    state.previous_purchase_contexts = [
        PurchaseContext(
            purchase_need="拍照好的手机",
            preferences={
                "target_category": "手机",
                "category": "数码电子",
                "canonical_target_key": "phone",
            },
            last_successful_items=[phone_item],
            last_items=[phone_item],
            target_category="手机",
            category="数码电子",
            canonical_target_key="phone",
        )
    ]
    state.last_successful_items = [skin_item]
    state.last_items = [skin_item]
    store.save(state)

    def restore_recommendation(query, top_k=3, negative_filters=None):
        return {
            "query": query,
            "filters": {
                "category": "数码电子",
                "max_price": None,
                "brand": None,
                "keywords": ["手机"],
            },
            "items": [phone_item],
        }

    monkeypatch.setattr(
        api_deps,
        "agent_runner",
        create_agent_runner(
            config=AppConfig(agent_runner="langgraph"),
            store=store,
            recommendation_tool=RecommendationTool(
                recommend_func=restore_recommendation
            ),
            understanding_service=FakeUnderstandingService(),
        ),
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "api-restore-confirm-session",
            "message": "对，就按之前的",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"session_id", "reply", "items", "state"}
    assert body["items"][0]["product_id"] == "p_restore_phone"
    assert body["state"]["action"] == "recommend"
    assert body["state"]["preferences"]["canonical_target_key"] == "phone"
    assert "pending_restore_category" not in body["state"]
    assert "pending_restore_display_target" not in body["state"]


def test_chat_tool_error_keeps_response_shape(monkeypatch):
    def fail_recommendation(query: str, top_k: int = 3):
        raise RuntimeError("boom")

    inject_recommend_chat_runner(
        monkeypatch,
        recommendation_tool=RecommendationTool(recommend_func=fail_recommendation),
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "test-chat-tool-error-session",
            "message": "recommend a camera phone under 9000",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"session_id", "reply", "items", "state"}
    assert payload["session_id"] == "test-chat-tool-error-session"
    assert payload["items"] == []
    assert "推荐服务暂时不可用" in payload["reply"]
    assert payload["state"]["action"] == "recommend"
    assert payload["state"]["result_status"] == "tool_error"
    assert payload["state"]["tool_error"] == "recommendation_failed"


def test_chat_stream_returns_sse_events(monkeypatch):
    inject_recommend_chat_runner(monkeypatch)

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "session_id": "test-stream-session",
            "message": "预算9000以内的拍照手机",
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode("utf-8")

    start_index = body.index("event: start")
    delta_index = body.index("event: delta")
    items_index = body.index("event: items")
    state_index = body.index("event: state")
    done_index = body.index("event: done")

    assert start_index < delta_index < items_index < state_index < done_index
    assert '"session_id": "test-stream-session"' in body
    assert '"product_id":' in body


def test_chat_stream_tool_error_returns_success_events(monkeypatch):
    def fail_recommendation(query: str, top_k: int = 3):
        raise RuntimeError("boom")

    inject_recommend_chat_runner(
        monkeypatch,
        recommendation_tool=RecommendationTool(recommend_func=fail_recommendation),
    )

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "session_id": "test-stream-tool-error-session",
            "message": "recommend a camera phone under 9000",
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode("utf-8")

    start_index = body.index("event: start")
    delta_index = body.index("event: delta")
    items_index = body.index("event: items")
    state_index = body.index("event: state")
    done_index = body.index("event: done")

    assert "event: error" not in body
    assert start_index < delta_index < items_index < state_index < done_index
    assert '"session_id": "test-stream-tool-error-session"' in body
    assert '"items": []' in body
    assert "推荐服务暂时不可用" in body
    assert '"result_status": "tool_error"' in body
    assert '"tool_error": "recommendation_failed"' in body


def test_chat_stream_negative_feedback_keeps_success_event_order(monkeypatch):
    store = InMemoryConversationStore()
    apple_item = ProductCard(
        product_id="p_apple_1",
        title="iPhone 15",
        brand="苹果",
        price=5999,
        reason="上一轮推荐",
        evidence="seed",
    )
    state = store.get_or_create("api-negative-stream-session")
    state.purchase_need = "想买一台拍照好的手机"
    state.preferences = {
        "target_category": "数码电子",
        "category": "数码电子",
        "focus": ["拍照"],
    }
    state.last_successful_items = [apple_item]
    state.last_items = [apple_item]

    def capture_recommendation(query, top_k=3, negative_filters=None):
        return {
            "query": query,
            "filters": {
                "category": "数码电子",
                "max_price": None,
                "brand": None,
                "keywords": ["拍照"],
            },
            "items": [
                ProductCard(
                    product_id="p_huawei_1",
                    title="华为 Mate 60",
                    brand="华为",
                    price=6999,
                    reason="避开苹果后的推荐",
                    evidence="test",
                )
            ],
        }

    monkeypatch.setattr(
        api_deps,
        "agent_runner",
        create_agent_runner(
            config=AppConfig(agent_runner="langgraph"),
            store=store,
            recommendation_tool=RecommendationTool(
                recommend_func=capture_recommendation
            ),
            understanding_service=FakeUnderstandingService(
                UserUnderstanding(
                    intent=UserIntent.UPDATE_PREFERENCE,
                    confidence=0.9,
                    negative_updates={"excluded_brands": ["苹果"]},
                )
            ),
        ),
    )

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "session_id": "api-negative-stream-session",
            "message": "不要苹果",
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode("utf-8")

    start_index = body.index("event: start")
    delta_index = body.index("event: delta")
    items_index = body.index("event: items")
    state_index = body.index("event: state")
    done_index = body.index("event: done")

    assert start_index < delta_index < items_index < state_index < done_index
    assert '"excluded_brands": ["苹果"]' in body
    assert '"applied": true' in body
    assert "event: error" not in body


def test_chat_stream_returns_error_event_when_agent_fails(monkeypatch):
    def fail_run(session_id: str, message: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(api_deps.agent_runner, "run", fail_run)

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "session_id": "test-stream-session",
            "message": "预算9000以内的拍照手机",
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert "event: error" in body
    assert "服务暂时不可用" in body
    assert body.index("event: start") < body.index("event: error")
    assert body.index("event: error") < body.index("event: done")


def test_chat_stream_returns_error_before_success_events_when_serialization_fails(
    monkeypatch,
):
    def run_with_unserializable_state(session_id: str, message: str):
        return ChatResponse(
            session_id=session_id,
            reply="这段回复不应先发送给客户端。",
            items=[],
            state={"bad": object()},
    )

    monkeypatch.setattr(api_deps.agent_runner, "run", run_with_unserializable_state)

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "session_id": "test-stream-session",
            "message": "预算9000以内的拍照手机",
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert "event: delta" not in body
    assert "event: items" not in body
    assert "event: state" not in body
    assert body.index("event: start") < body.index("event: error")
    assert body.index("event: error") < body.index("event: done")


def test_app_registers_split_api_routes():
    route_paths = {route.path for route in app.routes}

    assert "/" in route_paths
    assert "/health" in route_paths
    assert "/recommend" in route_paths
    assert "/rag/search" in route_paths
    assert "/chat" in route_paths
    assert "/chat/stream" in route_paths
