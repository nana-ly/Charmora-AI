from agent.understanding import UserIntent, UserUnderstanding
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
