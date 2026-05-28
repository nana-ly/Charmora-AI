from __future__ import annotations

import argparse
import json
import socket
import sys
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, TextIO
from urllib import error, request


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
EXIT_COMMANDS = {"exit", "quit", "q"}


class ChatCliError(RuntimeError):
    """Raised when a chat request cannot be completed."""


STREAM_READ_ERRORS = (
    TimeoutError,
    OSError,
    error.URLError,
    socket.timeout,
)
RECOVERABLE_STREAM_ERRORS = (ChatCliError, *STREAM_READ_ERRORS)


@dataclass(frozen=True)
class CliConfig:
    base_url: str
    mode: str
    session_id: str
    timeout: float


@dataclass(frozen=True)
class SseEvent:
    name: str
    data: dict[str, Any]


def build_chat_payload(session_id: str, message: str) -> bytes:
    payload = {
        "session_id": session_id,
        "message": message,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def endpoint_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def post_json(base_url: str, path: str, payload: bytes, timeout: float) -> dict[str, Any]:
    req = request.Request(
        endpoint_url(base_url, path),
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ChatCliError(f"HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise ChatCliError(str(exc.reason)) from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ChatCliError(f"invalid JSON response: {body}") from exc


def open_sse_stream(base_url: str, payload: bytes, timeout: float):
    req = request.Request(
        endpoint_url(base_url, "/chat/stream"),
        data=payload,
        method="POST",
        headers={
            "Accept": "text/event-stream",
            "Content-Type": "application/json; charset=utf-8",
        },
    )

    try:
        return request.urlopen(req, timeout=timeout)
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise ChatCliError(f"HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise ChatCliError(str(exc.reason)) from exc


def iter_sse_events(lines: Iterable[str]) -> Iterator[SseEvent]:
    event_name = "message"
    data_lines: list[str] = []

    def build_event() -> SseEvent | None:
        nonlocal event_name, data_lines
        if not data_lines:
            return None

        data_text = "\n".join(data_lines)
        try:
            data = json.loads(data_text)
        except json.JSONDecodeError:
            data = {"raw": data_text}

        event = SseEvent(event_name, data)
        event_name = "message"
        data_lines = []
        return event

    for line in lines:
        line = line.rstrip("\r\n")
        if line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line == "":
            event = build_event()
            if event is not None:
                yield event

    event = build_event()
    if event is not None:
        yield event


def parse_sse_events(lines: Iterable[str]) -> list[SseEvent]:
    return list(iter_sse_events(lines))


def stream_events(base_url: str, payload: bytes, timeout: float) -> list[SseEvent]:
    with open_sse_stream(base_url, payload, timeout) as response:
        decoded_lines = (
            raw_line.decode("utf-8", errors="replace") for raw_line in response
        )
        return parse_sse_events(decoded_lines)


def format_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def render_items(items: list[dict[str, Any]], output: TextIO) -> None:
    if not items:
        return

    output.write("\n推荐商品:\n")
    for index, item in enumerate(items, start=1):
        title = item.get("title", "")
        brand = item.get("brand", "")
        price = item.get("price", "")
        output.write(f"{index}. {title} | {brand} | ¥{price}\n")

        reason = item.get("reason")
        if reason:
            output.write(f"   理由: {reason}\n")

        evidence = item.get("evidence")
        if evidence:
            output.write(f"   依据: {evidence}\n")


def render_state(state: dict[str, Any], output: TextIO) -> None:
    if not state:
        return

    output.write("\n状态:\n")
    if "intent" in state:
        output.write(f"intent: {state['intent']}\n")
    if "preferences" in state:
        output.write(f"preferences: {format_json(state['preferences'])}\n")


def render_chat_response(payload: dict[str, Any], output: TextIO) -> None:
    reply = payload.get("reply", "")
    if reply:
        output.write("\n助手:\n")
        output.write(f"{reply}\n")

    render_items(payload.get("items", []), output)
    render_state(payload.get("state", {}), output)
    output.write("\n")


def render_sse_events(events: Iterable[SseEvent], output: TextIO) -> bool:
    saw_error = False
    items: list[dict[str, Any]] = []
    state: dict[str, Any] = {}

    output.write("\n助手:\n")
    for event in events:
        if event.name == "delta":
            output.write(event.data.get("text", ""))
            output.flush()
        elif event.name == "text":
            output.write(event.data.get("content", ""))
            output.flush()
        elif event.name == "items":
            items = event.data.get("items", [])
        elif event.name == "state":
            state = event.data.get("state", {})
        elif event.name == "error":
            saw_error = True
            output.write(f"[stream error] {format_json(event.data)}\n")

    output.write("\n")
    render_items(items, output)
    render_state(state, output)
    output.write("\n")
    return saw_error


def rest_chat_round(config: CliConfig, message: str, output: TextIO) -> None:
    payload = build_chat_payload(config.session_id, message)
    response = post_json(config.base_url, "/chat", payload, config.timeout)
    render_chat_response(response, output)


def stream_chat_round(config: CliConfig, message: str, output: TextIO) -> None:
    payload = build_chat_payload(config.session_id, message)
    try:
        with open_sse_stream(config.base_url, payload, config.timeout) as response:
            decoded_lines = (
                raw_line.decode("utf-8", errors="replace") for raw_line in response
            )
            saw_error = render_sse_events(iter_sse_events(decoded_lines), output)
    except STREAM_READ_ERRORS as exc:
        raise ChatCliError(str(exc)) from exc
    if saw_error:
        raise ChatCliError("stream returned error event")


def run_chat_round(config: CliConfig, message: str, output: TextIO) -> None:
    if config.mode == "rest":
        rest_chat_round(config, message, output)
        return

    try:
        stream_chat_round(config, message, output)
    except RECOVERABLE_STREAM_ERRORS as exc:
        output.write(f"\n[stream failed: {exc}; fallback to REST /chat]\n")
        rest_chat_round(config, message, output)


def create_config(args: argparse.Namespace) -> CliConfig:
    session_id = args.session or f"cli-{uuid.uuid4().hex[:8]}"
    return CliConfig(
        base_url=args.url,
        mode=args.mode,
        session_id=session_id,
        timeout=args.timeout,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual CLI client for testing ShopGuide chat endpoints.",
    )
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument(
        "--mode",
        choices=("stream", "rest"),
        default="stream",
        help="Use SSE stream mode or REST mode",
    )
    parser.add_argument("--session", help="Reuse a specific session_id")
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds",
    )
    return parser.parse_args(argv)


def configure_utf8_streams() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")


def interactive_loop(config: CliConfig, input_stream: TextIO, output: TextIO) -> int:
    output.write("ShopGuide 后端对话测试\n")
    output.write(f"Backend: {config.base_url}\n")
    output.write(f"Mode: {config.mode}\n")
    output.write(f"Session: {config.session_id}\n")
    output.write("\n输入问题，输入 exit/quit/q 退出。\n\n")

    while True:
        output.write("你 > ")
        output.flush()
        message = input_stream.readline()
        if message == "":
            output.write("\n")
            return 0

        message = message.strip()
        if not message:
            continue
        if message.lower() in EXIT_COMMANDS:
            output.write("已退出。\n")
            return 0

        try:
            run_chat_round(config, message, output)
        except ChatCliError as exc:
            output.write(f"\n[request failed: {exc}]\n")
            output.write(
                "请确认后端已启动，例如: uv run fastapi dev main.py --host "
                "127.0.0.1 --port 8000\n\n",
            )


def main(argv: list[str] | None = None) -> int:
    configure_utf8_streams()
    args = parse_args(argv)
    config = create_config(args)
    return interactive_loop(config, sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
