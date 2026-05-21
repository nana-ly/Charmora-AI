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
