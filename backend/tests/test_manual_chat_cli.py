from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path


def load_cli_module():
    module_path = Path(__file__).with_name("manual_chat_cli.py")
    assert module_path.exists(), "manual_chat_cli.py should exist"

    spec = importlib.util.spec_from_file_location(
        "manual_chat_cli_under_test",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_chat_payload_matches_frontend_contract():
    cli = load_cli_module()

    payload = json.loads(
        cli.build_chat_payload("session-1", "预算9000以内的拍照手机").decode("utf-8"),
    )

    assert payload == {
        "session_id": "session-1",
        "message": "预算9000以内的拍照手机",
    }


def test_parse_sse_events_reads_named_json_events():
    cli = load_cli_module()

    events = cli.parse_sse_events(
        [
            "event: start\n",
            'data: {"session_id": "session-1"}\n',
            "\n",
            "event: delta\n",
            'data: {"text": "这里是回复"}\n',
            "\n",
            "event: done\n",
            "data: {}\n",
            "\n",
        ],
    )

    assert [(event.name, event.data) for event in events] == [
        ("start", {"session_id": "session-1"}),
        ("delta", {"text": "这里是回复"}),
        ("done", {}),
    ]


def test_parse_sse_events_dispatches_final_event_without_blank_line():
    cli = load_cli_module()

    events = cli.parse_sse_events(
        [
            "event: done\n",
            "data: {}\n",
        ],
    )

    assert [(event.name, event.data) for event in events] == [("done", {})]


def test_render_sse_events_prints_delta_and_text_content_variants():
    cli = load_cli_module()
    out = io.StringIO()

    saw_error = cli.render_sse_events(
        [
            cli.SseEvent("delta", {"text": "第一段"}),
            cli.SseEvent("text", {"content": "第二段"}),
            cli.SseEvent(
                "items",
                {
                    "items": [
                        {
                            "title": "拍照旗舰手机",
                            "brand": "BrandX",
                            "price": 3999,
                        },
                    ],
                },
            ),
        ],
        out,
    )

    rendered = out.getvalue()
    assert saw_error is False
    assert "第一段第二段" in rendered
    assert "1. 拍照旗舰手机 | BrandX | ¥3999" in rendered


def test_render_chat_response_prints_reply_items_and_state():
    cli = load_cli_module()
    out = io.StringIO()

    cli.render_chat_response(
        {
            "reply": "我筛选了这几款商品。",
            "items": [
                {
                    "title": "拍照旗舰手机",
                    "brand": "BrandX",
                    "price": 3999,
                    "reason": "适合拍照需求",
                    "evidence": "命中拍照关键词",
                },
            ],
            "state": {
                "intent": "recommend",
                "preferences": {"category": "数码电子", "max_price": 9000},
            },
        },
        out,
    )

    rendered = out.getvalue()
    assert "助手:" in rendered
    assert "我筛选了这几款商品。" in rendered
    assert "1. 拍照旗舰手机 | BrandX | ¥3999" in rendered
    assert "理由: 适合拍照需求" in rendered
    assert "intent: recommend" in rendered
    assert '"max_price": 9000' in rendered


def test_run_chat_round_falls_back_to_rest_when_stream_fails(monkeypatch):
    cli = load_cli_module()
    out = io.StringIO()
    calls = []

    def fail_stream_round(config, message, output):
        raise cli.ChatCliError("stream unavailable")

    def fake_rest_round(config, message, output):
        calls.append((config.session_id, message))
        output.write("REST OK\n")

    monkeypatch.setattr(cli, "stream_chat_round", fail_stream_round)
    monkeypatch.setattr(cli, "rest_chat_round", fake_rest_round)

    config = cli.CliConfig(
        base_url="http://127.0.0.1:8000",
        mode="stream",
        session_id="session-1",
        timeout=1.0,
    )

    cli.run_chat_round(config, "hello", out)

    assert calls == [("session-1", "hello")]
    assert "stream failed: stream unavailable" in out.getvalue()
    assert "REST OK" in out.getvalue()


def test_run_chat_round_rest_mode_skips_stream(monkeypatch):
    cli = load_cli_module()
    out = io.StringIO()
    calls = []

    def fail_if_called(config, message, output):
        raise AssertionError("stream mode should not be used")

    def fake_rest_round(config, message, output):
        calls.append((config.session_id, message))
        output.write("REST OK\n")

    monkeypatch.setattr(cli, "stream_chat_round", fail_if_called)
    monkeypatch.setattr(cli, "rest_chat_round", fake_rest_round)

    config = cli.CliConfig(
        base_url="http://127.0.0.1:8000",
        mode="rest",
        session_id="session-1",
        timeout=1.0,
    )

    cli.run_chat_round(config, "hello", out)

    assert calls == [("session-1", "hello")]
    assert out.getvalue() == "REST OK\n"


def test_configure_utf8_streams_reconfigures_standard_streams(monkeypatch):
    cli = load_cli_module()

    class FakeStream:
        def __init__(self):
            self.calls = []

        def reconfigure(self, **kwargs):
            self.calls.append(kwargs)

    stdout = FakeStream()
    stderr = FakeStream()
    stdin = FakeStream()
    monkeypatch.setattr(cli.sys, "stdout", stdout)
    monkeypatch.setattr(cli.sys, "stderr", stderr)
    monkeypatch.setattr(cli.sys, "stdin", stdin)

    cli.configure_utf8_streams()

    assert stdout.calls == [{"encoding": "utf-8"}]
    assert stderr.calls == [{"encoding": "utf-8"}]
    assert stdin.calls == [{"encoding": "utf-8"}]
