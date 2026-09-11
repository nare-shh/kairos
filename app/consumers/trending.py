"""
Trending Leaderboard
════════════════════
Real-time "what's hot" ranking, built by the Kafka event worker from the
intent event stream (kairos.intent.events).

Storage: one Redis sorted set per hour bucket
    kairos:trending:{hour}  →  { product_id: summed intent weight }

Reading combines the current hour (full weight) with the previous hour
(half weight) — a cheap time decay without rewriting old scores.
"""

import time
from collections import defaultdict
from datetime import datetime

import redis.asyncio as aioredis

from app.services.pricing_engine import INTENT_WEIGHTS

TRENDING_KEY = "kairos:trending:{bucket}"
BUCKET_SECONDS = 3600
BUCKET_TTL_SECONDS = 2 * BUCKET_SECONDS + 60   # keep previous hour readable


def bucket_key(timestamp: float) -> str:
    return TRENDING_KEY.format(bucket=int(timestamp // BUCKET_SECONDS))


def _event_timestamp(message: dict) -> float:
    occurred_at = message.get("occurred_at")
    if occurred_at:
        try:
            return datetime.fromisoformat(occurred_at).timestamp()
        except (TypeError, ValueError):
            pass
    return time.time()


async def apply_intent_event(redis: aioredis.Redis, message: dict) -> bool:
    """
    Consumer handler: fold one intent event into the leaderboard.
    `message` is the envelope written by app.events.publisher.publish_event.
    Returns False for messages it doesn't understand (they are skipped).
    """
    product_id = message.get("aggregate_id")
    weight = INTENT_WEIGHTS.get(message.get("event_type", ""))
    if not product_id or weight is None:
        return False

    key = bucket_key(_event_timestamp(message))
    await redis.zincrby(key, weight, product_id)
    await redis.expire(key, BUCKET_TTL_SECONDS)
    return True


async def top_trending(
    redis: aioredis.Redis, limit: int = 8, now: float | None = None
) -> list[tuple[str, float]]:
    """Top products by decayed score — only positive scores (net demand) count."""
    now = time.time() if now is None else now
    scores: dict[str, float] = defaultdict(float)

    for key, factor in ((bucket_key(now), 1.0), (bucket_key(now - BUCKET_SECONDS), 0.5)):
        for member, score in await redis.zrevrange(key, 0, 199, withscores=True):
            scores[member] += score * factor

    ranked = sorted(
        ((pid, score) for pid, score in scores.items() if score > 0),
        key=lambda item: item[1],
        reverse=True,
    )
    return ranked[:limit]
