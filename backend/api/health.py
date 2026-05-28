from fastapi import APIRouter

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
