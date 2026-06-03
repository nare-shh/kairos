import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Order(Base):
    """
    An Order is created when a customer checks out their cart.

    Order lifecycle:
    ─────────────────────────────────────────────────────────
    pending_payment → paid → processing → shipped → delivered
                    ↘ payment_failed
                    ↘ cancelled
                    ↘ refunded

    Every transition is recorded as an event in the event_store.
    The status column here is just the CURRENT state for fast reads.
    The HISTORY lives in the event_store.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Human-readable order number shown to the customer
    # Format: ORD-2025-XXXXX (year + 5-char random hex)
    order_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )

    # Who placed the order
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        # RESTRICT: can't delete a user who has orders — protects data integrity
        nullable=False,
        index=True,
    )

    # Order lifecycle status
    status: Mapped[str] = mapped_column(
        Enum(
            "pending_payment",
            "paid",
            "processing",
            "shipped",
            "delivered",
            "cancelled",
            "payment_failed",
            "refunded",
            name="order_status_enum",
        ),
        default="pending_payment",
        nullable=False,
        index=True,
    )

    # ── Money fields (ALL Numeric — never Float for money!) ────────────────────
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
        # sum of (unit_price × quantity) for all items — before tax/shipping
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    shipping_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
        # total = subtotal + tax + shipping — what Stripe charges
    )

    # ── Stripe Integration ─────────────────────────────────────────────────────
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
        # Stripe's ID for this payment — used to look up payment status
        # Format: pi_3ABC123...
    )
    stripe_client_secret: Mapped[str | None] = mapped_column(
        Text, nullable=True
        # Sent to the frontend so it can complete payment with Stripe.js
        # Format: pi_3ABC123..._secret_XYZ
        # IMPORTANT: This is sensitive — don't log it or return it in list endpoints
    )

    # ── Delivery address (snapshot at time of order) ───────────────────────────
    # We store the address AS IT WAS when ordered — not a FK to an address table
    # Why? Addresses change. If a user moves, past orders should still show
    # the address they were shipped to. Snapshot = immutable copy.
    shipping_address: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # ── Metadata ──────────────────────────────────────────────────────────────
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
        # Only set when status transitions to "paid"
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        # cascade: if order is deleted, its items are deleted too
    )
    user: Mapped["User"] = relationship("User")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Order {self.order_number} status={self.status} total={self.total_amount}>"


class OrderItem(Base):
    """
    One line item in an order — one product × quantity.

    Prices are SNAPSHOTTED at the time of order.
    If the product's price changes after the order, this record is unchanged.
    This is critical: customers must be charged what they were shown.
    """

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Snapshot of product info at time of order
    # Why not just FK to products?
    # Because products can be renamed, deleted, or repriced later.
    # An order from 2024 must always show what was ordered at that time.
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # The price the customer actually paid (current_price at checkout time)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
        # = unit_price × quantity (pre-computed and stored for fast aggregation)
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")  # noqa: F821

    def __repr__(self) -> str:
        return f"<OrderItem product={self.product_sku} qty={self.quantity} price={self.unit_price}>"
