"""Initial schema — all Kairos tables

Revision ID: a1b2c3d4e5f6
Revises: (none — this is the first migration)
Create Date: 2026-06-01 00:00:00

This migration creates ALL tables from scratch.
When you run `alembic upgrade head` on a fresh database, this is the first thing that runs.

Why write this manually instead of auto-generating?
────────────────────────────────────────────────────
Auto-generation (`alembic revision --autogenerate`) works by comparing your models
against the live database. For the initial migration, the DB is empty, so autogenerate
would produce the same thing — but writing it manually forces you to understand every column.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None          # None = this is the first migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create all tables.
    Order matters — tables with foreign keys must be created AFTER their parents.
    users → categories → products → orders → order_items
    event_store has no FK dependencies → can go anywhere
    """

    # ── Create ENUM types first (PostgreSQL requires this) ────────────────────
    # Enums must exist before the table columns that use them
    user_role_enum = postgresql.ENUM(
        "customer", "seller", "admin",
        name="user_role_enum",
        create_type=False,  # we'll create it explicitly below
    )
    op.execute("CREATE TYPE user_role_enum AS ENUM ('customer', 'seller', 'admin')")
    op.execute("CREATE TYPE product_status_enum AS ENUM ('draft', 'active', 'inactive', 'deleted')")
    op.execute(
        "CREATE TYPE order_status_enum AS ENUM "
        "('pending_payment', 'paid', 'processing', 'shipped', 'delivered', "
        "'cancelled', 'payment_failed', 'refunded')"
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("customer", "seller", "admin", name="user_role_enum", create_constraint=False),
            nullable=False,
            server_default="customer",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── categories ────────────────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"],
            ondelete="SET NULL",
            name="fk_categories_parent_id",
        ),
    )
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    # ── products ──────────────────────────────────────────────────────────────
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
        sa.Column(
            "status",
            sa.Enum(
                "draft", "active", "inactive", "deleted",
                name="product_status_enum",
                create_constraint=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("images", postgresql.JSONB(), nullable=False, server_default="'[]'"),
        sa.Column("attributes", postgresql.JSONB(), nullable=False, server_default="'{}'"),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"],
            ondelete="SET NULL",
            name="fk_products_category_id",
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"], ["users.id"],
            ondelete="CASCADE",
            name="fk_products_seller_id",
        ),
    )
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)
    op.create_index("ix_products_sku", "products", ["sku"], unique=True)
    op.create_index("ix_products_seller_id", "products", ["seller_id"])
    op.create_index("ix_products_category_id", "products", ["category_id"])

    # ── event_store ───────────────────────────────────────────────────────────
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
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("caused_by", sa.String(255), nullable=True),
    )
    op.create_index("event_store_event_id_key", "event_store", ["event_id"], unique=True)
    op.create_index(
        "ix_event_store_aggregate",
        "event_store",
        ["aggregate_type", "aggregate_id"],
    )
    op.create_index("ix_event_store_type", "event_store", ["event_type"])
    op.create_index("ix_event_store_occurred_at", "event_store", ["occurred_at"])

    # ── orders ────────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending_payment", "paid", "processing", "shipped",
                "delivered", "cancelled", "payment_failed", "refunded",
                name="order_status_enum",
                create_constraint=False,
            ),
            nullable=False,
            server_default="pending_payment",
        ),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("stripe_client_secret", sa.Text(), nullable=True),
        sa.Column("shipping_address", postgresql.JSONB(), nullable=False, server_default="'{}'"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="RESTRICT",
            name="fk_orders_user_id",
        ),
    )
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index(
        "ix_orders_stripe_payment_intent_id",
        "orders",
        ["stripe_payment_intent_id"],
    )

    # ── order_items ───────────────────────────────────────────────────────────
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
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"],
            ondelete="CASCADE",
            name="fk_order_items_order_id",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            ondelete="RESTRICT",
            name="fk_order_items_product_id",
        ),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])


def downgrade() -> None:
    """
    Drop everything in REVERSE order of creation.
    Tables with FK dependencies must be dropped BEFORE their parents.
    order_items → orders → products → categories → users → event_store
    """
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("event_store")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("users")

    # Drop ENUM types last — they can't be dropped while columns reference them
    op.execute("DROP TYPE IF EXISTS order_status_enum")
    op.execute("DROP TYPE IF EXISTS product_status_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
