"""
Trending leaderboard — the Kafka worker's handler, tested without Kafka.
"""

import time

from app.consumers.trending import BUCKET_SECONDS, apply_intent_event, top_trending


def message(product_id: str, event_type: str, occurred_at: str | None = None) -> dict:
    # Same envelope shape as app.events.publisher.publish_event
    return {"aggregate_id": product_id, "event_type": event_type, "occurred_at": occurred_at}


async def test_products_are_ranked_by_intent_weight(fake_redis):
    await apply_intent_event(fake_redis, message("viewed", "ProductViewed"))
    await apply_intent_event(fake_redis, message("carted", "CartAdded"))
    await apply_intent_event(fake_redis, message("viewed", "ProductViewed"))

    assert await top_trending(fake_redis) == [("carted", 5.0), ("viewed", 2.0)]


async def test_net_negative_demand_is_not_trending(fake_redis):
    await apply_intent_event(fake_redis, message("p1", "CartRemoved"))
    assert await top_trending(fake_redis) == []


async def test_unknown_messages_are_skipped(fake_redis):
    assert await apply_intent_event(fake_redis, message("p1", "SomethingElse")) is False
    assert await apply_intent_event(fake_redis, {"event_type": "CartAdded"}) is False
    assert await top_trending(fake_redis) == []


async def test_previous_hour_counts_half(fake_redis):
    now = time.time()
    from datetime import datetime, timezone
    last_hour = datetime.fromtimestamp(now - BUCKET_SECONDS, tz=timezone.utc).isoformat()

    await apply_intent_event(fake_redis, message("old", "CartAdded", occurred_at=last_hour))
    await apply_intent_event(fake_redis, message("new", "ProductViewed"))
    await apply_intent_event(fake_redis, message("new", "ProductViewed"))
    await apply_intent_event(fake_redis, message("new", "ProductViewed"))

    assert await top_trending(fake_redis, now=now) == [("new", 3.0), ("old", 2.5)]
