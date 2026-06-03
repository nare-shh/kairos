import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Product(Base):
    """
    Product state table — the READ MODEL in CQRS.

    IMPORTANT CONCEPT — CQRS (Command Query Responsibility Segregation):
    ─────────────────────────────────────────────────────────────────────
    WRITE side: EventStore table → append-only, never updated
    READ side:  Product table   → updated to reflect current state

    Flow:
        User requests price change
            → Service saves "ProductPriceChanged" event to event_store
            → Service ALSO updates the price column here (the "projection")
            → API reads from HERE (fast, simple SQL) not from event_store

    Why two places?
        event_store = the truth (what happened, history, audit)
        products    = the view (what is current, optimized for reading)

    The products table is essentially a CACHE of the current state
    derived from replaying all events. If it gets corrupted, replay all
    events from event_store and it will be perfect again.
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
        # SKU = Stock Keeping Unit — unique product identifier used in inventory
    )

    # ── Pricing (Kairos core!) ────────────────────────────────────────────────
    # Numeric(10, 2) = up to 10 digits total, 2 decimal places
    # e.g. 99999999.99 is the max — more than enough for any product
    # We use Numeric (fixed-point), NOT Float (floating-point)
    # because Float has rounding errors: 0.1 + 0.2 = 0.30000000000000004
    # With money, rounding errors = legal problems. Always use Numeric.

    base_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
        # base_price = what the seller set. Never changes unless seller edits it.
    )
    current_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
        # current_price = what buyers see NOW. Kairos adjusts this dynamically.
    )
    min_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
        # min_price = floor set by seller. Kairos will never price below this.
    )
    max_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
        # max_price = ceiling set by seller. Kairos will never price above this.
    )

    # ── Inventory ─────────────────────────────────────────────────────────────
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # low_stock_threshold: when stock drops below this, trigger a "low stock" alert
    # Low stock + high demand = Kairos raises price
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # ── Status ────────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Enum("draft", "active", "inactive", "deleted", name="product_status_enum"),
        default="draft",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Images ────────────────────────────────────────────────────────────────
    # JSONB array of image URLs — simpler than a separate images table for now
    # e.g. ["https://cdn.kairos.dev/products/abc/1.jpg", "..."]
    images: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # ── Kairos metadata ───────────────────────────────────────────────────────
    # Extra flexible data stored as JSON
    # Sellers can add: weight, dimensions, color, material — anything
    # Without needing a schema change (no new columns)
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # ── Relationships ─────────────────────────────────────────────────────────
    # Foreign key to categories
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped["Category | None"] = relationship(  # noqa: F821
        "Category", back_populates="products"
    )

    # Foreign key to user (the seller who owns this product)
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller: Mapped["User"] = relationship("User")  # noqa: F821

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

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name} price={self.current_price}>"
