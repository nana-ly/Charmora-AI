import logging
from collections.abc import Iterator
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api import deps
from core.request_context import set_request_context
from schemas.chat import ChatRequest, ChatResponse
from sse import sse_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    """执行一轮多轮导购对话。"""
    request_id = http_request.headers.get("X-Request-ID") or uuid4().hex
    with set_request_context(request_id=request_id, session_id=request.session_id):
        logger.info(
            "chat request received session_id=%s message_length=%s",
            request.session_id,
            len(request.message),
        )
        response = deps.run_chat(request.session_id, request.message)
        logger.info(
            "chat response generated session_id=%s item_count=%s",
            request.session_id,
            len(response.items),
        )
    return response


@router.post("/chat/stream")
def chat_stream(request: ChatRequest, http_request: Request) -> StreamingResponse:
    """用 SSE 事件流返回一轮对话结果。"""
    request_id = http_request.headers.get("X-Request-ID") or uuid4().hex
    with set_request_context(request_id=request_id, session_id=request.session_id):
        logger.info(
            "chat stream request received session_id=%s message_length=%s",
            request.session_id,
            len(request.message),
        )

    def event_generator() -> Iterator[str]:
        yield sse_event("start", {"session_id": request.session_id})

        try:
            with set_request_context(request_id=request_id, session_id=request.session_id):
                response = deps.run_chat(request.session_id, request.message)
                logger.info(
                    "chat stream response generated session_id=%s item_count=%s",
                    request.session_id,
                    len(response.items),
                )
                success_events = [
                    sse_event("delta", {"text": response.reply}),
                    sse_event(
                        "items",
                        {
                            "items": [item.model_dump() for item in response.items],
                            "result_count": response.result_count,
                        },
                    ),
                    sse_event("state", {"state": response.state}),
                ]
            yield from success_events
        except Exception:
            with set_request_context(request_id=request_id, session_id=request.session_id):
                logger.exception("chat stream failed")
            yield sse_event(
                "error",
                {"message": "服务暂时不可用，请稍后再试。"},
            )
        finally:
            yield sse_event("done")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
