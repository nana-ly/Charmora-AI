import inspect
import logging
import queue
import re
import threading
from collections.abc import Iterator
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from api import deps
from core.request_context import set_request_context
from schemas.chat import ChatRequest, ChatResponse
from schemas.product import ProductCard
from sse import sse_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    """Run one multi-turn shopping-agent turn."""
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
    """Stream a shopping-agent turn as SSE events."""
    request_id = http_request.headers.get("X-Request-ID") or uuid4().hex
    with set_request_context(request_id=request_id, session_id=request.session_id):
        logger.info(
            "chat stream request received session_id=%s message_length=%s",
            request.session_id,
            len(request.message),
        )

    def event_generator() -> Iterator[str]:
        yield sse_event(
            "start", {"session_id": request.session_id, "request_id": request_id}
        )

        evt_queue: queue.Queue[dict] = queue.Queue()

        def node_cb(event: str, node: str, detail: str):
            evt_queue.put(
                {
                    "type": "thinking",
                    "event": event,
                    "node": node,
                    "detail": detail,
                }
            )

        def run_agent():
            try:
                with set_request_context(
                    request_id=request_id,
                    session_id=request.session_id,
                ):
                    if _supports_node_callback(deps.run_chat):
                        response = deps.run_chat(
                            request.session_id,
                            request.message,
                            node_callback=node_cb,
                        )
                    else:
                        response = deps.run_chat(request.session_id, request.message)
                    evt_queue.put({"type": "response", "response": response})
            except Exception:
                with set_request_context(
                    request_id=request_id,
                    session_id=request.session_id,
                ):
                    logger.exception("chat stream failed")
                evt_queue.put(
                    {"type": "error", "message": "服务暂时不可用，请稍后再试。"}
                )

        thread = threading.Thread(target=run_agent, daemon=True)
        thread.start()

        try:
            while True:
                try:
                    event = evt_queue.get(timeout=0.1)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue

                if event["type"] == "thinking":
                    yield sse_event(
                        "thinking",
                        {
                            "event": event["event"],
                            "node": event["node"],
                            "detail": event["detail"],
                        },
                    )
                    continue

                if event["type"] == "response":
                    response = event["response"]
                    yield from _response_events(response)
                    break

                if event["type"] == "error":
                    yield sse_event("error", {"message": event["message"]})
                    break
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


def _response_events(response: ChatResponse) -> Iterator[str]:
    blocks = response.content_blocks or _parse_content_blocks(response.reply, response.items)
    if blocks:
        for block in blocks:
            if block.get("type") == "text":
                yield sse_event("delta", {"text": block.get("content", "")})
            elif block.get("type") == "card":
                yield sse_event("card", {"item": block.get("item", {})})
    else:
        yield sse_event("delta", {"text": response.reply})

    yield sse_event(
        "items",
        {
            "items": [item.model_dump() for item in response.items],
            "result_count": response.result_count,
        },
    )
    yield sse_event("state", {"state": response.state})


def _supports_node_callback(func) -> bool:
    signature = inspect.signature(func)
    return (
        "node_callback" in signature.parameters
        or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )
    )


def _parse_content_blocks(reply: str, items: list[ProductCard]) -> list[dict]:
    """Split [INSERT:n] markers into text and product-card blocks."""
    if not items:
        return [{"type": "text", "content": reply}]

    blocks: list[dict] = []
    parts = re.split(r"\[INSERT:(\d+)\]", reply)
    for index, part in enumerate(parts):
        if index % 2 == 0:
            text = part.strip()
            if text:
                blocks.append({"type": "text", "content": text})
            continue

        item_index = int(part)
        if 0 <= item_index < len(items):
            blocks.append(
                {"type": "card", "index": item_index, "item": _item_to_dict(items[item_index])}
            )
    return blocks or [{"type": "text", "content": reply}]


def _item_to_dict(item: ProductCard) -> dict:
    return {
        "product_id": item.product_id,
        "sku_id": item.sku_id,
        "title": item.title,
        "brand": item.brand,
        "price": item.price,
        "reason": item.reason,
        "evidence": item.evidence,
        "image_url": item.image_url,
        "imageUrl": item.imageUrl,
        "rating": item.rating,
        "sold_count": item.sold_count,
        "review_count": item.review_count,
        "marketing_desc": item.marketing_desc,
        "reviews": [
            review.model_dump() if hasattr(review, "model_dump") else review
            for review in (item.reviews or [])
        ],
        "faqs": [
            faq.model_dump() if hasattr(faq, "model_dump") else faq
            for faq in (item.faqs or [])
        ],
        "price_range": item.price_range,
    }
