from pathlib import Path

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


def _mount_product_images() -> None:
    if not config.product_image_static_enabled:
        return
    if "://" in config.product_image_base_url:
        return

    mount_path = "/" + config.product_image_base_url.strip("/")
    if mount_path == "/":
        return

    static_root = Path(config.product_image_static_root)
    if not static_root.is_absolute():
        static_root = Path(__file__).resolve().parent / static_root
    app.mount(
        mount_path,
        StaticFiles(directory=str(static_root.resolve()), check_dir=False),
        name="product_images",
    )


_mount_product_images()


__all__ = ["app"]
