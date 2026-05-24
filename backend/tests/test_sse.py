from sse import sse_event


def test_sse_event_formats_named_event_with_json_data():
    event = sse_event("delta", {"text": "你好"})

    assert event == 'event: delta\ndata: {"text": "你好"}\n\n'


def test_sse_event_uses_empty_object_when_data_is_missing():
    event = sse_event("done")

    assert event == "event: done\ndata: {}\n\n"
