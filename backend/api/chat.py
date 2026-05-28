import logging
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api import deps
from schemas.chat import ChatRequest, ChatResponse
from sse import sse_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """执行一轮多轮导购对话。"""
    logger.info("chat request received session_id=%s", request.session_id)
    logger.debug("chat message_length=%s", len(request.message))
    response = deps.run_chat(request.session_id, request.message)
    logger.info("chat response generated session_id=%s item_count=%s", request.session_id, len(response.items))
    return response


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """用 SSE 事件流返回一轮对话结果。"""
    logger.info("chat stream request received session_id=%s", request.session_id)

    def event_generator() -> Iterator[str]:
        yield sse_event("start", {"session_id": request.session_id})

        try:
            response = deps.run_chat(request.session_id, request.message)
            logger.info("chat stream response generated session_id=%s", request.session_id)
            success_events = [
                sse_event("delta", {"text": response.reply}),
                sse_event(
                    "items",
                    {"items": [item.model_dump() for item in response.items]},
                ),
                sse_event("state", {"state": response.state}),
            ]
            yield from success_events
        except Exception:
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
