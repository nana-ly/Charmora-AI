"""请求级日志上下文。

使用 contextvars 可以让 FastAPI 请求、SSE 生成器和 Runner 内部日志共享同一组
request/session/turn 标识；没有上下文时统一输出 '-'，避免 formatter 缺字段。
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from contextvars import ContextVar, Token


@dataclass(frozen=True)
class RequestContext:
    """当前日志上下文字段。"""

    request_id: str = "-"
    session_id: str = "-"
    turn_id: str = "-"


_request_id: ContextVar[str] = ContextVar("request_id", default="-")
_session_id: ContextVar[str] = ContextVar("session_id", default="-")
_turn_id: ContextVar[str] = ContextVar("turn_id", default="-")


def get_request_context() -> RequestContext:
    """读取当前上下文；供日志 filter 注入到每条记录。"""
    return RequestContext(
        request_id=_request_id.get(),
        session_id=_session_id.get(),
        turn_id=_turn_id.get(),
    )


@contextmanager
def set_request_context(
    *,
    request_id: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
) -> Iterator[RequestContext]:
    """临时设置日志上下文，并在异常路径中自动恢复。"""
    tokens: list[tuple[ContextVar[str], Token[str]]] = []
    if request_id is not None:
        tokens.append((_request_id, _request_id.set(request_id or "-")))
    if session_id is not None:
        tokens.append((_session_id, _session_id.set(session_id or "-")))
    if turn_id is not None:
        tokens.append((_turn_id, _turn_id.set(turn_id or "-")))

    try:
        yield get_request_context()
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)
