import logging

from fastapi import APIRouter

from schemas.recommend import RecommendRequest
from services.recommendation_service import run_recommendation

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/recommend", response_model=None)
def recommend(request: RecommendRequest) -> dict:
    """执行推荐链路。"""
    logger.info("recommend request received")
    logger.debug("recommend query_length=%s", len(request.query))
    result = run_recommendation(request.query)
    logger.info("recommend response generated item_count=%s", len(result.get("items", [])))
    return result
