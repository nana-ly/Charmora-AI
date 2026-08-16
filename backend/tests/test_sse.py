import api.deps as api_deps
from agent.understanding import UserIntent, UserUnderstanding
from schemas.chat import ChatResponse
from sse import sse_event
from test_main import (
    FakeUnderstandingService,
    client,
    inject_recommend_chat_runner,
)


def test_sse_event_formats_named_event_with_json_data():
    event = sse_event("delta", {"text": "你好"})

    assert event == 'event: delta\ndata: {"text": "你好"}\n\n'


def test_sse_event_uses_empty_object_when_data_is_missing():
    event = sse_event("done")

    assert event == "event: done\ndata: {}\n\n"


def test_chat_stream_exposes_canonical_target_key(monkeypatch):
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

    with client.stream(
        "POST",
        "/chat/stream",
        json={"session_id": "sse-canonical", "message": "推荐手机"},
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert '"canonical_target_key": "phone"' in body
    assert '"is_broad_category_request": true' in body


def test_chat_stream_tool_error_uses_success_event_order(monkeypatch):
    monkeypatch.setattr(
        api_deps,
        "run_chat",
        lambda session_id, message: ChatResponse(
            session_id=session_id,
            reply="推荐服务暂时不可用，请稍后再试。",
            items=[],
            state={
                "intent": "recommend",
                "action": "recommend",
                "result_status": "tool_error",
                "tool_error": "recommendation_failed",
            },
        ),
    )

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "session_id": "sse-tool-error-contract",
            "message": "推荐拍照手机",
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    start_index = body.index("event: start")
    delta_index = body.index("event: delta")
    items_index = body.index("event: items")
    state_index = body.index("event: state")
    done_index = body.index("event: done")

    assert start_index < delta_index < items_index < state_index < done_index
    assert "event: error" not in body
    assert '"result_status": "tool_error"' in body
    assert '"tool_error": "recommendation_failed"' in body


def test_chat_stream_card_keeps_sku_id_for_android_cart(monkeypatch):
    from schemas.product import ProductCard

    monkeypatch.setattr(
        api_deps,
        "run_chat",
        lambda session_id, message: ChatResponse(
            session_id=session_id,
            reply="推荐如下 [INSERT:0]",
            items=[
                ProductCard(
                    product_id="550e8400-e29b-41d4-a716-446655440000",
                    sku_id="550e8400-e29b-41d4-a716-446655440001",
                    title="Test item",
                    brand="Test",
                    price=19.9,
                    reason="match",
                    evidence="truth",
                )
            ],
            state={"action": "recommend"},
        ),
    )

    with client.stream(
        "POST",
        "/chat/stream",
        json={"session_id": "sse-card-sku", "message": "recommend"},
    ) as response:
        body = response.read().decode("utf-8")

    assert 'event: card' in body
    assert '"sku_id": "550e8400-e29b-41d4-a716-446655440001"' in body
    assert '"request_id":' in body


def test_chat_stream_unhandled_exception_uses_error_then_done(monkeypatch):
    def fail_run_chat(session_id, message):
        raise RuntimeError("boom")

    monkeypatch.setattr(api_deps, "run_chat", fail_run_chat)

    with client.stream(
        "POST",
        "/chat/stream",
        json={
            "session_id": "sse-unhandled-error-contract",
            "message": "推荐拍照手机",
        },
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    start_index = body.index("event: start")
    error_index = body.index("event: error")
    done_index = body.index("event: done")

    assert start_index < error_index < done_index
    assert "event: delta" not in body
    assert "服务暂时不可用，请稍后再试。" in body
