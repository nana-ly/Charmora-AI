import logging

from fastapi import APIRouter, Header, Query

from api.deps import run_recommendation
from core.config import load_app_config
from schemas.recommend import RecommendRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/recommend", response_model=None)
def recommend(
    request: RecommendRequest,
    debug: bool = Query(default=False),
    x_debug_trace: str | None = Header(default=None),
) -> dict:
    """执行推荐链路。"""
    logger.info("recommend request received")
    logger.debug("recommend query_length=%s", len(request.query))
    include_trace = _should_include_trace(
        body_debug=request.debug,
        query_debug=debug,
        header_debug=x_debug_trace,
    )
    if include_trace:
        result = run_recommendation(request.query, include_trace=True)
    else:
        result = run_recommendation(request.query)
    logger.info("recommend response generated item_count=%s", len(result.get("items", [])))
    return result


def _should_include_trace(
    *,
    body_debug: bool,
    query_debug: bool,
    header_debug: str | None,
) -> bool:
    """同时满足服务端开关和请求显式 debug，才暴露脱敏 trace。"""
    if not load_app_config().recommend_trace_enabled:
        return False
    header_enabled = str(header_debug or "").lower() == "true"
    return body_debug or query_debug or header_enabled
