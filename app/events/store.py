"""
Event Store helpers — the single way to append to event_store.

Every append computes the next version for its aggregate, so the event
sequence of each product / order is gap-free: 1, 2, 3, ...
(Previously automated events were hard-coded to version=1, which broke
the per-aggregate ordering that event sourcing relies on.)
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_store import EventStore


async def next_version(db: AsyncSession, aggregate_type: str, aggregate_id: str) -> int:
    """Next version number for an aggregate's event stream."""
    # autoflush makes events added earlier in this transaction visible here
    result = await db.execute(
        select(func.max(EventStore.version)).where(
            EventStore.aggregate_type == aggregate_type,
            EventStore.aggregate_id == aggregate_id,
        )
    )
    return (result.scalar_one_or_none() or 0) + 1


async def append_event(
    db: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict,
    caused_by: str | None = None,
    metadata: dict | None = None,
) -> EventStore:
    """Append one immutable event (flushed, committed with the surrounding transaction)."""
    event = EventStore(
        event_id=uuid.uuid4(),
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        version=await next_version(db, aggregate_type, aggregate_id),
        caused_by=caused_by,
        metadata_=metadata or {},
    )
    db.add(event)
    await db.flush()
    return event
