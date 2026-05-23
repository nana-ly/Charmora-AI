from fastapi import FastAPI
from pydantic import BaseModel

from recommendation import recommend_products


app = FastAPI(title="ShopGuide RAG API")


class RecommendRequest(BaseModel):
    """推荐接口请求体，接收用户的自然语言需求。"""

    query: str


@app.get("/")
def read_root() -> dict[str, str]:
    """返回服务基础信息，用于确认后端应用已经启动。"""
    return {
        "name": "ShopGuide RAG API",
        "status": "running",
    }


@app.get("/health")
def read_health() -> dict[str, str]:
    """健康检查接口，用于验证 FastAPI 服务是否可访问。"""
    return {"status": "ok"}


@app.post("/recommend")
def recommend(request: RecommendRequest) -> dict:
    """推荐接口：调用完整推荐链路，并保证异常时也返回稳定商品卡片。"""
    return recommend_products(request.query)
