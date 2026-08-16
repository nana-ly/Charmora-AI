"""Add checkout preview and simulated fulfillment fields."""

from alembic import op
import sqlalchemy as sa

revision = "20260816_0002"
down_revision = "20260814_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("recipient_name", sa.String(100), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("recipient_phone", sa.String(30), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("shipping_address", sa.String(500), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("customer_note", sa.String(500), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("payment_method", sa.String(30), nullable=False, server_default="demo_wechat"))
    op.add_column("orders", sa.Column("payment_status", sa.String(30), nullable=False, server_default="simulated_paid"))
    op.add_column("orders", sa.Column("idempotency_key", sa.String(100), nullable=True))
    op.create_index("ix_orders_idempotency_key", "orders", ["idempotency_key"])
    op.create_unique_constraint("uq_order_idempotency_key", "orders", ["idempotency_key"])
    op.create_table(
        "checkout_previews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(100), nullable=False),
        sa.Column("session_id", sa.String(200), nullable=False),
        sa.Column("cart_signature", sa.String(64), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_checkout_previews_token", "checkout_previews", ["token"], unique=True)
    op.create_index("ix_checkout_previews_session_id", "checkout_previews", ["session_id"])


def downgrade() -> None:
    op.drop_table("checkout_previews")
    op.drop_constraint("uq_order_idempotency_key", "orders", type_="unique")
    op.drop_index("ix_orders_idempotency_key", table_name="orders")
    for column in (
        "idempotency_key", "payment_status", "payment_method", "customer_note",
        "shipping_address", "recipient_phone", "recipient_name",
    ):
        op.drop_column("orders", column)
