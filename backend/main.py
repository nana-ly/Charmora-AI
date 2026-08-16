import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.chat import router as chat_router
from api.catalog import router as catalog_router
from api.commerce import cart_router, order_router
from api.imports import router as imports_router
from api.vector_sync import router as vector_sync_router
from api.multimodal import router as multimodal_router
from api.health import router as health_router
from api.rag import router as rag_router
from api.recommend import router as recommend_router
from core.config import load_app_config
from core.errors import AppError, ErrorBody
from core.request_context import get_request_context, set_request_context
from core.logging_config import configure_logging


config = load_app_config()
configure_logging(config.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    from api.catalog import database_runtime

    runtime = database_runtime()
    if config.database.url.startswith("sqlite"):
        from services.demo_catalog import bootstrap_demo_catalog

        bootstrap_demo_catalog(runtime)
    elif config.catalog_source == "postgresql":
        runtime.check_connection()
        runtime.check_migration(config.database.expected_revision)
    yield


app = FastAPI(title="ShopGuide RAG API", lifespan=lifespan)
app.include_router(health_router)
app.include_router(recommend_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(catalog_router)
app.include_router(cart_router)
app.include_router(order_router)
app.include_router(imports_router)
app.include_router(vector_sync_router)
app.include_router(multimodal_router)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    with set_request_context(request_id=request_id):
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


def _error_response(request: Request, *, code: str, message: str, status_code: int, details=None):
    context = get_request_context()
    request_id = context.request_id or request.headers.get("X-Request-ID") or uuid4().hex
    body = ErrorBody(
        code=code,
        message=message,
        request_id=request_id,
        details=details or {},
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


@app.exception_handler(RequestValidationError)
def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(
        request,
        code="validation_error",
        message="请求参数无效。",
        status_code=422,
        details={"errors": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(
        request,
        code="http_error",
        message=str(exc.detail),
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("unhandled request error", exc_info=exc)
    return _error_response(
        request,
        code="internal_error",
        message="服务暂时不可用，请稍后重试。",
        status_code=500,
    )


# 挂载商品图片静态目录，前端通过 /static/xxx.jpg 访问
dataset_root = os.path.join(os.path.dirname(__file__), "..", "ecommerce_agent_dataset")
app.mount("/static", StaticFiles(directory=dataset_root), name="static")


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
