"""
Background Repricer
═══════════════════
Demand signals live in a 1-hour sliding window in Redis. When a product goes
quiet its score decays — but prices only change when something triggers a
re-evaluation. Without this loop, a product that surged at 2pm would stay
surge-priced forever once people stopped looking at it.

Every REPRICE_INTERVAL_SECONDS it re-scores every product that either
- still has live intent signals in Redis, or
- is currently priced away from its base price.

Products nobody has interacted with keep their base price (no signal = no change).
A Redis lock makes sure only one API replica runs each cycle.
"""

import asyncio
import logging
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import AsyncSessionLocal
from app.models.product import Product
from app.services.pricing_engine import PricingEngine
from app.services.repricing import broadcast, reprice_product

logger = logging.getLogger(__name__)

LOCK_KEY = "kairos:repricer:lock"


async def find_candidates(db: AsyncSession, redis: aioredis.Redis) -> set[uuid.UUID]:
    """Products with live demand signals OR a price that has drifted from base."""
    candidates: set[uuid.UUID] = set()

    intent_prefix = PricingEngine.INTENT_KEY.format(product_id="")
    async for key in redis.scan_iter(match=f"{intent_prefix}*", count=500):
        try:
            candidates.add(uuid.UUID(key[len(intent_prefix):]))
        except ValueError:
            continue

    drifted = await db.execute(
        select(Product.id).where(
            Product.is_active == True,  # noqa: E712
            Product.current_price != Product.base_price,
        )
    )
    candidates.update(drifted.scalars().all())
    return candidates


async def run_reprice_cycle(redis: aioredis.Redis) -> int:
    """Reprice every candidate product once. Returns how many prices changed."""
    engine = PricingEngine(redis)

    async with AsyncSessionLocal() as db:
        candidates = await find_candidates(db, redis)
        if not candidates:
            return 0

        result = await db.execute(
            select(Product).where(
                Product.id.in_(candidates),
                Product.is_active == True,  # noqa: E712
            )
        )
        changes = []
        for product in result.scalars().all():
            _, change = await reprice_product(db, engine, product, trigger="demand_decay")
            if change:
                changes.append(change)

        await db.commit()

    # Broadcast only after the new prices are durable
    for change in changes:
        await broadcast(engine, change)
    return len(changes)


async def repricer_loop(interval_seconds: int) -> None:
    """Runs for the lifetime of the API process (started in main.lifespan)."""
    logger.info(f"Repricer started (every {interval_seconds}s)")
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            redis = get_redis()
            # SET NX EX = "take the lock if nobody holds it" — one replica per cycle
            if not await redis.set(LOCK_KEY, "1", nx=True, ex=max(interval_seconds - 1, 1)):
                continue
            changed = await run_reprice_cycle(redis)
            if changed:
                logger.info(f"Repricer adjusted {changed} price(s)")
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never let one bad cycle kill the loop
            logger.exception("Repricer cycle failed")
