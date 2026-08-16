from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.config import load_app_config
from core.errors import AppError
from db.repositories.products import ProductRepository
from db.session import DatabaseRuntime, create_database_runtime
from schemas.catalog import CategoryListResponse, InventoryView, ProductListResponse, ProductView
from services.catalog_service import CatalogNotFoundError, CatalogService

router = APIRouter(tags=["catalog"])


@lru_cache(maxsize=1)
def database_runtime() -> DatabaseRuntime:
    return create_database_runtime(load_app_config().database)


def get_db() -> Iterator[Session]:
    yield from database_runtime().session()


def get_catalog_service(session: Session = Depends(get_db)) -> CatalogService:
    return CatalogService(ProductRepository(session))


@router.get("/categories", response_model=CategoryListResponse)
def list_categories(service: CatalogService = Depends(get_catalog_service)) -> CategoryListResponse:
    return CategoryListResponse(items=service.list_categories())


@router.get("/products", response_model=ProductListResponse)
def list_products(
    category_id: UUID | None = None,
    query: str | None = Query(default=None, max_length=200),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    in_stock: bool | None = None,
    sort: str = Query(default="newest", pattern="^(newest|price_asc|price_desc|title)$"),
    active_only: bool = True,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    service: CatalogService = Depends(get_catalog_service),
) -> ProductListResponse:
    filters = dict(
            category_id=category_id,
            active_only=active_only,
            query=query,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
        )
    return ProductListResponse(
        items=service.list_products(offset=offset, limit=limit, sort=sort, **filters),
        offset=offset,
        limit=limit,
        total=service.count_products(**filters),
    )


@router.get("/products/{product_id}", response_model=ProductView)
def get_product(
    product_id: UUID,
    service: CatalogService = Depends(get_catalog_service),
) -> ProductView:
    try:
        return service.get_product(product_id)
    except CatalogNotFoundError as exc:
        raise AppError("product_not_found", "商品不存在。", status_code=404) from exc


@router.get("/products/{product_id}/inventory", response_model=InventoryView)
def get_inventory(
    product_id: UUID,
    service: CatalogService = Depends(get_catalog_service),
) -> InventoryView:
    product = get_product(product_id, service)
    return InventoryView(product_id=product.id, skus=product.skus)
