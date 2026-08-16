from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.errors import AppError
from db.models import CartItem, CheckoutPreview, Order, OrderItem, OrderStatusEvent, ProductPrice, ProductSku
from db.repositories.commerce import CommerceRepository
from schemas.commerce import (
    CartItemView,
    CartView,
    CheckoutPreviewView,
    CreateOrderRequest,
    OrderItemView,
    OrderListResponse,
    OrderStatusEventView,
    OrderView,
)


class CommerceService:
    """Transaction boundary for cart and simulated order mutations."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = CommerceRepository(session)

    def get_cart(self, session_id: str) -> CartView:
        cart = self.repository.get_cart(session_id)
        return self._cart_view(session_id, cart.items if cart else [])

    def add_item(self, session_id: str, sku_id: UUID, quantity: int) -> CartView:
        try:
            with self.session.begin():
                sku = self._require_sellable_sku(sku_id)
                cart = self.repository.get_or_create_cart(session_id)
                existing = next((item for item in cart.items if item.sku_id == sku_id), None)
                requested = quantity + (existing.quantity if existing else 0)
                self._validate_stock(sku, requested)
                if existing:
                    existing.quantity = requested
                else:
                    cart.items.append(CartItem(sku_id=sku_id, quantity=quantity))
            return self.get_cart(session_id)
        except AppError:
            self.session.rollback()
            raise

    def update_item(self, session_id: str, sku_id: UUID, quantity: int) -> CartView:
        try:
            with self.session.begin():
                cart = self.repository.get_cart(session_id, lock=True)
                item = self._require_cart_item(cart, sku_id)
                sku = self._require_sellable_sku(sku_id)
                self._validate_stock(sku, quantity)
                item.quantity = quantity
            return self.get_cart(session_id)
        except AppError:
            self.session.rollback()
            raise

    def remove_item(self, session_id: str, sku_id: UUID) -> CartView:
        with self.session.begin():
            cart = self.repository.get_cart(session_id, lock=True)
            item = self._require_cart_item(cart, sku_id)
            self.session.delete(item)
        return self.get_cart(session_id)

    def clear_cart(self, session_id: str) -> CartView:
        with self.session.begin():
            cart = self.repository.get_cart(session_id, lock=True)
            if cart:
                for item in list(cart.items):
                    self.session.delete(item)
        return CartView(session_id=session_id)

    def preview_checkout(self, session_id: str) -> CheckoutPreviewView:
        with self.session.begin():
            cart = self.repository.get_cart(session_id, lock=True)
            if cart is None or not cart.items:
                raise AppError("cart_empty", "购物车为空，无法结算。", status_code=409)
            for item in cart.items:
                sku = self._require_sellable_sku(item.sku_id)
                self._validate_stock(sku, item.quantity)
            cart_view = self._cart_view(session_id, list(cart.items))
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
            preview = CheckoutPreview(
                token=uuid4().hex,
                session_id=session_id,
                cart_signature=self._cart_signature(cart.items),
                total_amount=cart_view.total_amount,
                expires_at=expires_at,
            )
            self.session.add(preview)
            self.session.flush()
            token = preview.token
        return CheckoutPreviewView(
            confirmation_token=token,
            session_id=session_id,
            items=cart_view.items,
            total_amount=cart_view.total_amount,
            currency=cart_view.currency,
            expires_at=expires_at,
        )

    def checkout(self, session_id: str, request: CreateOrderRequest | None = None) -> OrderView:
        try:
            with self.session.begin():
                if request and request.idempotency_key:
                    existing = self.repository.get_order_by_idempotency_key(request.idempotency_key)
                    if existing is not None:
                        return self._order_view(existing)
                cart = self.repository.get_cart(session_id, lock=True)
                if cart is None or not cart.items:
                    raise AppError("cart_empty", "购物车为空，无法下单。", status_code=409)

                preview = None
                if request and request.confirmation_token:
                    preview = self.repository.get_preview(request.confirmation_token, lock=True)
                    now = datetime.now(timezone.utc)
                    if preview is None or preview.session_id != session_id:
                        raise AppError("checkout_preview_invalid", "结算确认已失效，请重新确认。", status_code=409)
                    if preview.consumed_at is not None or _aware(preview.expires_at) <= now:
                        raise AppError("checkout_preview_expired", "结算确认已过期，请重新确认。", status_code=409)
                    if preview.cart_signature != self._cart_signature(cart.items):
                        raise AppError("cart_changed", "购物车或商品信息已变化，请重新确认。", status_code=409)

                order = Order(
                    session_id=session_id,
                    status="preparing",
                    recipient_name=request.recipient_name if request else "演示用户",
                    recipient_phone=request.recipient_phone if request else "13800000000",
                    shipping_address=request.shipping_address if request else "演示地址",
                    customer_note=request.customer_note if request else "",
                    payment_method=request.payment_method if request else "demo_wechat",
                    payment_status="simulated_paid",
                    idempotency_key=request.idempotency_key if request else None,
                )
                self.session.add(order)
                total = Decimal("0")
                for cart_item in sorted(cart.items, key=lambda item: str(item.sku_id)):
                    sku = self._require_sellable_sku(cart_item.sku_id)
                    self._validate_stock(sku, cart_item.quantity)
                    price = _current_price(sku.prices)
                    if price is None:
                        raise AppError("price_unavailable", "商品当前价格不可用。", status_code=409)
                    sku.inventory.available_quantity -= cart_item.quantity
                    sku.inventory.version += 1
                    subtotal = price.amount * cart_item.quantity
                    total += subtotal
                    image_url = sku.product.images[0].url if sku.product.images else None
                    order.items.append(
                        OrderItem(
                            sku_id=sku.id,
                            product_id=sku.product_id,
                            quantity=cart_item.quantity,
                            unit_price=price.amount,
                            product_title=sku.product.title,
                            sku_name=sku.name,
                            image_url=image_url,
                        )
                    )
                order.total_amount = total
                order.status_events.extend(
                    [
                        OrderStatusEvent(from_status=None, to_status="created", reason="订单已确认"),
                        OrderStatusEvent(from_status="created", to_status="paid", reason="演示支付成功"),
                        OrderStatusEvent(from_status="paid", to_status="preparing", reason="商品备货中"),
                    ]
                )
                if preview is not None:
                    preview.consumed_at = datetime.now(timezone.utc)
                for item in list(cart.items):
                    self.session.delete(item)
                self.session.flush()
            return self.get_order(order.id)
        except AppError:
            self.session.rollback()
            raise

    def list_orders(self, session_id: str, *, offset: int, limit: int) -> OrderListResponse:
        orders, total = self.repository.list_orders(session_id, offset=offset, limit=limit)
        return OrderListResponse(
            items=[self._order_view(order) for order in orders],
            offset=offset,
            limit=limit,
            total=total,
        )

    def complete_order(self, order_id: UUID) -> OrderView:
        with self.session.begin():
            order = self.repository.get_order(order_id, lock=True)
            if order is None:
                raise AppError("order_not_found", "订单不存在。", status_code=404)
            if order.status == "completed":
                return self._order_view(order)
            if order.status != "preparing":
                raise AppError("order_not_completable", "当前订单状态不可完成。", status_code=409)
            order.status_events.append(
                OrderStatusEvent(from_status="preparing", to_status="completed", reason="演示订单已完成")
            )
            order.status = "completed"
        return self.get_order(order_id)

    def get_order(self, order_id: UUID) -> OrderView:
        order = self.repository.get_order(order_id)
        if order is None:
            raise AppError("order_not_found", "订单不存在。", status_code=404)
        return self._order_view(order)

    def cancel_order(self, order_id: UUID) -> OrderView:
        try:
            with self.session.begin():
                order = self.repository.get_order(order_id, lock=True)
                if order is None:
                    raise AppError("order_not_found", "订单不存在。", status_code=404)
                if order.status not in {"created", "preparing"}:
                    raise AppError("order_not_cancellable", "当前订单状态不可取消。", status_code=409)
                for item in sorted(order.items, key=lambda value: str(value.sku_id)):
                    sku = self.repository.lock_sku_inventory(item.sku_id)
                    if sku is None or sku.inventory is None:
                        raise AppError("inventory_unavailable", "库存记录不可用，取消失败。", status_code=409)
                    sku.inventory.available_quantity += item.quantity
                    sku.inventory.version += 1
                previous = order.status
                order.status = "cancelled"
                order.cancelled_at = datetime.now(timezone.utc)
                order.status_events.append(
                    OrderStatusEvent(
                        from_status=previous,
                        to_status="cancelled",
                        reason="用户取消模拟订单",
                    )
                )
            return self.get_order(order_id)
        except AppError:
            self.session.rollback()
            raise

    def _require_sellable_sku(self, sku_id: UUID) -> ProductSku:
        sku = self.repository.lock_sellable_sku(sku_id)
        if sku is None:
            raise AppError("sku_unavailable", "商品规格不存在或已下架。", status_code=404)
        return sku

    @staticmethod
    def _validate_stock(sku: ProductSku, quantity: int) -> None:
        available = sku.inventory.available_quantity if sku.inventory else 0
        if quantity > available:
            raise AppError(
                "insufficient_inventory",
                "库存不足。",
                status_code=409,
                details={"available_quantity": available},
            )

    @staticmethod
    def _require_cart_item(cart, sku_id: UUID) -> CartItem:
        if cart is None:
            raise AppError("cart_item_not_found", "购物车中没有该商品。", status_code=404)
        item = next((value for value in cart.items if value.sku_id == sku_id), None)
        if item is None:
            raise AppError("cart_item_not_found", "购物车中没有该商品。", status_code=404)
        return item

    @staticmethod
    def _cart_signature(items: list[CartItem]) -> str:
        values: list[str] = []
        for item in sorted(items, key=lambda value: str(value.sku_id)):
            price = _current_price(item.sku.prices)
            inventory_version = item.sku.inventory.version if item.sku.inventory else -1
            values.append(
                f"{item.sku_id}:{item.quantity}:{price.amount if price else 'none'}:{inventory_version}"
            )
        return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()

    @classmethod
    def _cart_view(cls, session_id: str, items: list[CartItem]) -> CartView:
        views: list[CartItemView] = []
        total = Decimal("0")
        for item in items:
            price = _current_price(item.sku.prices)
            if price is None:
                continue
            product = item.sku.product
            image_url = product.images[0].url if product.images else None
            available = item.sku.inventory.available_quantity if item.sku.inventory else 0
            views.append(
                CartItemView(
                    sku_id=item.sku_id,
                    product_id=product.id,
                    title=product.title,
                    sku_name=item.sku.name,
                    quantity=item.quantity,
                    available_quantity=available,
                    unit_price=price.amount,
                    currency=price.currency,
                    image_url=image_url,
                )
            )
            total += price.amount * item.quantity
        return CartView(session_id=session_id, items=views, total_amount=total)

    @staticmethod
    def _order_view(order: Order) -> OrderView:
        return OrderView(
            id=order.id,
            session_id=order.session_id,
            status=order.status,
            total_amount=order.total_amount,
            currency=order.currency,
            recipient_name=order.recipient_name,
            recipient_phone=order.recipient_phone,
            shipping_address=order.shipping_address,
            customer_note=order.customer_note,
            payment_method=order.payment_method,
            payment_status=order.payment_status,
            created_at=order.created_at,
            cancelled_at=order.cancelled_at,
            items=[
                OrderItemView(
                    sku_id=item.sku_id,
                    product_id=item.product_id,
                    product_title=item.product_title,
                    sku_name=item.sku_name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    image_url=item.image_url,
                )
                for item in order.items
            ],
            status_events=[
                OrderStatusEventView(
                    from_status=event.from_status,
                    to_status=event.to_status,
                    reason=event.reason,
                    created_at=event.created_at,
                )
                for event in sorted(order.status_events, key=lambda value: value.created_at)
            ],
        )


def _current_price(prices: list[ProductPrice]) -> ProductPrice | None:
    now = datetime.now(timezone.utc)
    valid = [
        price
        for price in prices
        if _aware(price.valid_from) <= now
        and (price.valid_to is None or _aware(price.valid_to) > now)
    ]
    return max(valid, key=lambda value: _aware(value.valid_from), default=None)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
