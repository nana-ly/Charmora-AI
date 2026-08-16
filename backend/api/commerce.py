from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.catalog import get_db
from schemas.commerce import (
    AddCartItemRequest,
    CartView,
    CheckoutPreviewRequest,
    CheckoutPreviewView,
    CreateOrderRequest,
    OrderListResponse,
    OrderView,
    UpdateCartItemRequest,
)
from services.commerce_service import CommerceService

cart_router = APIRouter(prefix="/cart", tags=["cart"])
order_router = APIRouter(prefix="/orders", tags=["orders"])


def get_commerce_service(session: Session = Depends(get_db)) -> CommerceService:
    return CommerceService(session)


@cart_router.get("/{session_id}", response_model=CartView)
def get_cart(session_id: str, service: CommerceService = Depends(get_commerce_service)) -> CartView:
    return service.get_cart(session_id)


@cart_router.post("/{session_id}/items", response_model=CartView)
def add_cart_item(
    session_id: str,
    request: AddCartItemRequest,
    service: CommerceService = Depends(get_commerce_service),
) -> CartView:
    return service.add_item(session_id, request.sku_id, request.quantity)


@cart_router.patch("/{session_id}/items/{sku_id}", response_model=CartView)
def update_cart_item(
    session_id: str,
    sku_id: UUID,
    request: UpdateCartItemRequest,
    service: CommerceService = Depends(get_commerce_service),
) -> CartView:
    return service.update_item(session_id, sku_id, request.quantity)


@cart_router.delete("/{session_id}/items/{sku_id}", response_model=CartView)
def remove_cart_item(
    session_id: str,
    sku_id: UUID,
    service: CommerceService = Depends(get_commerce_service),
) -> CartView:
    return service.remove_item(session_id, sku_id)


@cart_router.delete("/{session_id}", response_model=CartView)
def clear_cart(session_id: str, service: CommerceService = Depends(get_commerce_service)) -> CartView:
    return service.clear_cart(session_id)


@order_router.post("", response_model=OrderView, status_code=status.HTTP_201_CREATED)
def create_order(
    request: CreateOrderRequest,
    service: CommerceService = Depends(get_commerce_service),
) -> OrderView:
    return service.checkout(request.session_id, request)


@order_router.post("/preview", response_model=CheckoutPreviewView)
def preview_order(
    request: CheckoutPreviewRequest,
    service: CommerceService = Depends(get_commerce_service),
) -> CheckoutPreviewView:
    return service.preview_checkout(request.session_id)


@order_router.get("", response_model=OrderListResponse)
def list_orders(
    session_id: str = Query(min_length=1, max_length=200),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: CommerceService = Depends(get_commerce_service),
) -> OrderListResponse:
    return service.list_orders(session_id, offset=offset, limit=limit)


@order_router.get("/{order_id}", response_model=OrderView)
def get_order(order_id: UUID, service: CommerceService = Depends(get_commerce_service)) -> OrderView:
    return service.get_order(order_id)


@order_router.post("/{order_id}/cancel", response_model=OrderView)
def cancel_order(order_id: UUID, service: CommerceService = Depends(get_commerce_service)) -> OrderView:
    return service.cancel_order(order_id)


@order_router.post("/{order_id}/complete", response_model=OrderView)
def complete_order(order_id: UUID, service: CommerceService = Depends(get_commerce_service)) -> OrderView:
    return service.complete_order(order_id)
