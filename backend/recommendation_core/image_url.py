"""商品图片 URL 组装工具。"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from core.config import load_app_config


def get_product_image_path(product: dict[str, Any]) -> str | None:
    """读取并规范化商品数据中的相对图片路径。"""
    raw_path = product.get("image_path")
    if raw_path is None:
        return None
    image_path = str(raw_path).strip().replace("\\", "/").lstrip("/")
    return image_path or None


def build_product_image_url(
    image_path: str | None,
    base_url: str | None = None,
) -> str | None:
    """把商品相对图片路径转换为可访问 URL。"""
    if not image_path:
        return None

    base = (
        base_url
        if base_url is not None
        else load_app_config().product_image_base_url
    ).strip()
    if not base:
        return _encode_path(image_path)

    return f"{base.rstrip('/')}/{_encode_path(image_path)}"


def product_image_fields(product: dict[str, Any]) -> dict[str, str | None]:
    """返回商品卡片兼容使用的图片字段。"""
    image_path = get_product_image_path(product)
    image_url = build_product_image_url(image_path)
    return {
        "image_path": image_path,
        "image_url": image_url,
        "imageUrl": image_url,
    }


def _encode_path(image_path: str) -> str:
    normalized = image_path.replace("\\", "/").lstrip("/")
    return "/".join(quote(segment, safe="") for segment in normalized.split("/"))
