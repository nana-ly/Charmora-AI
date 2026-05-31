from fastapi import APIRouter, Response, status

import api.deps as api_deps

router = APIRouter()


@router.get("/")
def read_root() -> dict[str, str]:
    """返回服务基本信息。"""
    return {
        "name": "ShopGuide RAG API",
        "status": "running",
    }


@router.get("/health")
def read_health() -> dict[str, str]:
    """返回健康检查状态。"""
    return {"status": "ok"}


@router.get("/ready")
def read_ready(response: Response) -> dict:
    """返回推荐依赖可用性；/health 只代表进程存活。"""
    payload = api_deps.recommendation_service.ready()
    if payload.get("status") != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload
