import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.chat import router as chat_router
from api.health import router as health_router
from api.rag import router as rag_router
from api.recommend import router as recommend_router
from core.config import load_app_config
from core.logging_config import configure_logging


config = load_app_config()
configure_logging(config.log_level)

app = FastAPI(title="ShopGuide RAG API")
app.include_router(health_router)
app.include_router(recommend_router)
app.include_router(rag_router)
app.include_router(chat_router)

# 挂载商品图片静态目录，前端通过 /static/xxx.jpg 访问
dataset_root = os.path.join(os.path.dirname(__file__), "..", "ecommerce_agent_dataset")
app.mount("/static", StaticFiles(directory=dataset_root), name="static")


__all__ = ["app"]
