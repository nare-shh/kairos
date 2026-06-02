import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EventStore(Base):
    """
    THE HEART OF KAIROS — The immutable event log.

    In traditional systems you UPDATE rows:
        UPDATE products SET price = 99 WHERE id = 1

    In event sourcing you APPEND events:
        INSERT INTO event_store (aggregate_type, aggregate_id, event_type, payload)
        VALUES ('product', 1, 'ProductPriceChanged', {"old": 120, "new": 99, "reason": "demand_drop"})

    Why is this powerful?
    ─────────────────────
    1. FULL HISTORY: You can see EVERY change ever made + who made it + why
    2. REPLAY: Delete the products table, replay all events → products table is rebuilt perfectly
    3. AUDIT: "Why is this price $99?" → Look at the event log, the answer is always there
    4. TIME TRAVEL: Reconstruct state at ANY point in time
    5. DEBUGGING: When something goes wrong, you have the full story

    This is how banks, trading systems, and fraud detection work internally.
    """

    __tablename__ = "event_store"

    # Sequence number — guaranteed ordering of events (auto-increments)
    # BigInteger because over time this can get very large (millions of events)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Event ID — globally unique identifier for this specific event
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # Aggregate = the "thing" this event is about
    # Examples: "product", "order", "user", "cart"
    # In DDD (Domain-Driven Design) language: the root entity that owns this event
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # The ID of the specific aggregate instance
    # e.g., if aggregate_type = "product", this is the product's UUID
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # The event type — describes WHAT happened, in past tense (domain language)
    # Examples: "ProductCreated", "ProductPriceChanged", "ProductDeactivated"
    # Using past tense is intentional: events are facts that already happened
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # The event payload — all the data about what happened
    # JSONB (not JSON) in PostgreSQL:
    # - Stored in binary format → faster to query
    # - Can be indexed → can search inside JSON fields
    # - Supports operators like @>, ?, @? for JSON queries
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Metadata about the event itself (not the business data)
    # Store: who triggered it, from which IP, which service, correlation ID etc.
    metadata_: Mapped[dict] = mapped_column(
        "metadata",           # actual column name in DB (metadata_ is just Python name)
        JSONB,
        nullable=False,
        default=dict,
    )

    # Version — optimistic concurrency control
    # Each event for the same aggregate increments this
    # Before saving a new event, you check: is the current version what I expected?
    # If not → someone else changed it → conflict → retry
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    # When this event was recorded — NEVER updated, only set on insert
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Who caused this event — user ID (nullable because system events have no user)
    caused_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Indexes ───────────────────────────────────────────────────────────────
    # Composite index on (aggregate_type, aggregate_id):
    # "Give me all events for product X" — this query runs constantly
    # Without an index: full table scan → slow as hell with millions of rows
    # With an index: direct lookup → microseconds
    __table_args__ = (
        Index("ix_event_store_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_event_store_type", "event_type"),
        Index("ix_event_store_occurred_at", "occurred_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Event id={self.id} type={self.event_type} "
            f"aggregate={self.aggregate_type}:{self.aggregate_id}>"
        )
