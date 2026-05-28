import json
from collections.abc import Mapping
from typing import Any


def sse_event(event: str, data: Mapping[str, Any] | None = None) -> str:
    payload = json.dumps(data or {}, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
