from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


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


def test_recommend_returns_three_product_cards_from_loaded_products():
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


def test_chat_returns_agent_response_and_state():
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
