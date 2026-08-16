"""Create catalog, import, cart and simulated-order schema."""

from alembic import op

from db.base import Base
import db.models  # noqa: F401

revision = "20260814_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is the immutable bootstrap revision for the first PostgreSQL business schema.
    # All model additions after this revision must use explicit follow-up migrations.
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for table_name in (
        "order_status_events",
        "order_items",
        "orders",
        "cart_items",
        "carts",
        "vector_sync_jobs",
        "product_images",
        "product_prices",
        "inventory",
        "product_skus",
        "products",
        "import_batches",
        "data_sources",
        "categories",
    ):
        op.drop_table(table_name)
