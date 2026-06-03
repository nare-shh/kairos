"""Initial schema — all Kairos tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-01 00:00:00
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy import inspect, text
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _type_exists(conn, name: str) -> bool:
    """Query pg_type catalog — works on ALL PostgreSQL versions."""
    result = conn.execute(
        text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": name},
    )
    return result.fetchone() is not None


# Pre-declare enum types with create_type=False
# This tells SQLAlchemy: "these types already exist in the DB, do NOT create them"
# Using postgresql.ENUM (not sa.Enum) — only the dialect-specific class respects create_type=False
user_role = PGEnum("customer", "seller", "admin", name="user_role_enum", create_type=False)
product_status = PGEnum("draft", "active", "inactive", "deleted", name="product_status_enum", create_type=False)
order_status = PGEnum(
    "pending_payment", "paid", "processing", "shipped", "delivered",
    "cancelled", "payment_failed", "refunded",
    name="order_status_enum", create_type=False
)


def upgrade() -> None:
    conn = op.get_bind()
    existing = inspect(conn).get_table_names()

    # Create enum types only if they don't exist (pg_type catalog is universal)
    if not _type_exists(conn, "user_role_enum"):
        op.execute("CREATE TYPE user_role_enum AS ENUM ('customer', 'seller', 'admin')")
    if not _type_exists(conn, "product_status_enum"):
        op.execute("CREATE TYPE product_status_enum AS ENUM ('draft', 'active', 'inactive', 'deleted')")
    if not _type_exists(conn, "order_status_enum"):
        op.execute(
            "CREATE TYPE order_status_enum AS ENUM "
            "('pending_payment','paid','processing','shipped','delivered',"
            "'cancelled','payment_failed','refunded')"
        )

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=True),
            sa.Column("hashed_password", sa.Text(), nullable=False),
            sa.Column("role", user_role, nullable=False, server_default="customer"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "categories" not in existing:
        op.create_table(
            "categories",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_categories_name", "categories", ["name"], unique=True)
        op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    if "products" not in existing:
        op.create_table(
            "products",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("slug", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sku", sa.String(100), nullable=False),
            sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("current_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("min_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("max_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("status", product_status, nullable=False, server_default="draft"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("images", postgresql.JSONB(), nullable=False, server_default="'[]'"),
            sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="'{}'"),
            sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_products_slug", "products", ["slug"], unique=True)
        op.create_index("ix_products_sku", "products", ["sku"], unique=True)
        op.create_index("ix_products_name", "products", ["name"])
        op.create_index("ix_products_seller_id", "products", ["seller_id"])
        op.create_index("ix_products_category_id", "products", ["category_id"])

    if "event_store" not in existing:
        op.create_table(
            "event_store",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("aggregate_type", sa.String(100), nullable=False),
            sa.Column("aggregate_id", sa.String(255), nullable=False),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="'{}'"),
            sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="'{}'"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("caused_by", sa.String(255), nullable=True),
        )
        op.create_index("event_store_event_id_key", "event_store", ["event_id"], unique=True)
        op.create_index("ix_event_store_aggregate", "event_store", ["aggregate_type", "aggregate_id"])
        op.create_index("ix_event_store_type", "event_store", ["event_type"])
        op.create_index("ix_event_store_occurred_at", "event_store", ["occurred_at"])

    if "orders" not in existing:
        op.create_table(
            "orders",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("order_number", sa.String(50), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("status", order_status, nullable=False, server_default="pending_payment"),
            sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
            sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
            sa.Column("stripe_client_secret", sa.Text(), nullable=True),
            sa.Column("shipping_address", postgresql.JSONB(), nullable=False, server_default="'{}'"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        )
        op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
        op.create_index("ix_orders_user_id", "orders", ["user_id"])
        op.create_index("ix_orders_status", "orders", ["status"])
        op.create_index("ix_orders_stripe_payment_intent_id", "orders", ["stripe_payment_intent_id"])

    if "order_items" not in existing:
        op.create_table(
            "order_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("product_name", sa.String(255), nullable=False),
            sa.Column("product_sku", sa.String(100), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        )
        op.create_index("ix_order_items_order_id", "order_items", ["order_id"])


def downgrade() -> None:
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("event_store")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS order_status_enum")
    op.execute("DROP TYPE IF EXISTS product_status_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
