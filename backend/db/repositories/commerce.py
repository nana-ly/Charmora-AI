from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from db.models import (
    Cart,
    CartItem,
    CheckoutPreview,
    Order,
    Product,
    ProductPrice,
    ProductSku,
)


class CommerceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_cart(self, session_id: str, *, lock: bool = False) -> Cart | None:
        statement = (
            select(Cart)
            .where(Cart.session_id == session_id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.sku)
                .selectinload(ProductSku.product)
                .selectinload(Product.images),
                selectinload(Cart.items)
                .selectinload(CartItem.sku)
                .selectinload(ProductSku.inventory),
                selectinload(Cart.items)
                .selectinload(CartItem.sku)
                .selectinload(ProductSku.prices),
            )
        )
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_or_create_cart(self, session_id: str) -> Cart:
        cart = self.get_cart(session_id)
        if cart is None:
            cart = Cart(session_id=session_id)
            self.session.add(cart)
            self.session.flush()
        return cart

    def lock_sellable_sku(self, sku_id: UUID) -> ProductSku | None:
        now = datetime.now(timezone.utc)
        statement = (
            select(ProductSku)
            .join(ProductSku.product)
            .join(ProductSku.inventory)
            .join(ProductSku.prices)
            .where(
                ProductSku.id == sku_id,
                ProductSku.active.is_(True),
                Product.active.is_(True),
                ProductPrice.valid_from <= now,
                or_(ProductPrice.valid_to.is_(None), ProductPrice.valid_to > now),
            )
            .options(
                selectinload(ProductSku.product).selectinload(Product.images),
                selectinload(ProductSku.inventory),
                selectinload(ProductSku.prices),
            )
            .with_for_update()
        )
        return self.session.scalar(statement)

    def lock_sku_inventory(self, sku_id: UUID) -> ProductSku | None:
        """Lock inventory for compensation even when a product was later downlisted."""
        statement = (
            select(ProductSku)
            .join(ProductSku.inventory)
            .where(ProductSku.id == sku_id)
            .options(selectinload(ProductSku.inventory))
            .with_for_update()
        )
        return self.session.scalar(statement)

    def get_order(self, order_id: UUID, *, lock: bool = False) -> Order | None:
        statement = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.status_events))
        )
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def get_order_by_idempotency_key(self, key: str) -> Order | None:
        return self.session.scalar(
            select(Order)
            .where(Order.idempotency_key == key)
            .options(selectinload(Order.items), selectinload(Order.status_events))
        )

    def list_orders(self, session_id: str, *, offset: int, limit: int) -> tuple[list[Order], int]:
        base = select(Order).where(Order.session_id == session_id)
        total = self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        statement = (
            base.options(selectinload(Order.items), selectinload(Order.status_events))
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement)), int(total)

    def get_preview(self, token: str, *, lock: bool = False) -> CheckoutPreview | None:
        statement = select(CheckoutPreview).where(CheckoutPreview.token == token)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)
