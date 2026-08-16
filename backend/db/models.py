from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(40))
    authorized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("data_sources.id"), index=True)
    filename: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_product_source_external"),
        Index("ix_products_category_active", "category_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("data_sources.id"), index=True)
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500), index=True)
    brand: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    import_batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("import_batches.id"))

    skus: Mapped[list[ProductSku]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    category: Mapped[Category] = relationship()
    source: Mapped[DataSource] = relationship()


class ProductSku(TimestampMixin, Base):
    __tablename__ = "product_skus"
    __table_args__ = (UniqueConstraint("product_id", "external_id", name="uq_sku_product_external"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(300), default="默认规格")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(back_populates="skus")
    inventory: Mapped[Inventory | None] = relationship(
        back_populates="sku", cascade="all, delete-orphan", uselist=False
    )
    prices: Mapped[list[ProductPrice]] = relationship(
        back_populates="sku", cascade="all, delete-orphan"
    )


class Inventory(TimestampMixin, Base):
    __tablename__ = "inventory"

    sku_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_skus.id", ondelete="CASCADE"), primary_key=True
    )
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)

    sku: Mapped[ProductSku] = relationship(back_populates="inventory")


class ProductPrice(Base):
    __tablename__ = "product_prices"
    __table_args__ = (Index("ix_product_prices_sku_valid", "sku_id", "valid_from", "valid_to"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sku_id: Mapped[UUID] = mapped_column(ForeignKey("product_skus.id", ondelete="CASCADE"), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sku: Mapped[ProductSku] = relationship(back_populates="prices")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    alt_text: Mapped[str] = mapped_column(String(500), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    product: Mapped[Product] = relationship(back_populates="images")


class VectorSyncJob(TimestampMixin, Base):
    __tablename__ = "vector_sync_jobs"
    __table_args__ = (Index("ix_vector_sync_jobs_status_created", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    operation: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Cart(TimestampMixin, Base):
    __tablename__ = "carts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "sku_id", name="uq_cart_item_sku"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cart_id: Mapped[UUID] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    sku_id: Mapped[UUID] = mapped_column(ForeignKey("product_skus.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    cart: Mapped[Cart] = relationship(back_populates="items")
    sku: Mapped[ProductSku] = relationship()


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_order_idempotency_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(30), default="created", index=True)
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    recipient_name: Mapped[str] = mapped_column(String(100), default="")
    recipient_phone: Mapped[str] = mapped_column(String(30), default="")
    shipping_address: Mapped[str] = mapped_column(String(500), default="")
    customer_note: Mapped[str] = mapped_column(String(500), default="")
    payment_method: Mapped[str] = mapped_column(String(30), default="demo_wechat")
    payment_status: Mapped[str] = mapped_column(String(30), default="simulated_paid")
    idempotency_key: Mapped[str | None] = mapped_column(String(100), index=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    status_events: Mapped[list[OrderStatusEvent]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class CheckoutPreview(TimestampMixin, Base):
    __tablename__ = "checkout_previews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(200), index=True)
    cart_signature: Mapped[str] = mapped_column(String(64))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    sku_id: Mapped[UUID] = mapped_column(ForeignKey("product_skus.id"), index=True)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    product_title: Mapped[str] = mapped_column(String(500))
    sku_name: Mapped[str] = mapped_column(String(300))
    image_url: Mapped[str | None] = mapped_column(String(1000))
    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusEvent(Base):
    __tablename__ = "order_status_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    order: Mapped[Order] = relationship(back_populates="status_events")
