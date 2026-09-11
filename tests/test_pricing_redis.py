"""
Pricing engine ↔ Redis: how intent signals are recorded and scored.
Uses an in-memory fake Redis — no server needed.
"""

import json
import time

from app.services.pricing_engine import PricingEngine


async def test_score_sums_event_weights(fake_redis):
    engine = PricingEngine(fake_redis)
    for _ in range(3):
        await engine.record_intent("p1", "CartAdded", session_id="s1")

    score = await engine.compute_score("p1")
    assert score["demand_score"] == 15.0
    assert score["demand_level"] == "high"
    assert score["cart_adds_1h"] == 3


async def test_negative_signals_reduce_the_score(fake_redis):
    engine = PricingEngine(fake_redis)
    await engine.record_intent("p1", "CartAdded")
    await engine.record_intent("p1", "CartRemoved")

    score = await engine.compute_score("p1")
    assert score["demand_score"] == 1.0
    assert score["demand_level"] == "low"


async def test_events_outside_the_window_are_ignored(fake_redis):
    stale = json.dumps({"type": "CartAdded", "ts": time.time() - PricingEngine.WINDOW_SECONDS - 60})
    await fake_redis.lpush(PricingEngine.INTENT_KEY.format(product_id="p1"), stale)

    score = await PricingEngine(fake_redis).compute_score("p1")
    assert score["demand_score"] == 0
    assert score["event_counts"] == {}


async def test_unique_viewers_are_counted_per_session(fake_redis):
    engine = PricingEngine(fake_redis)
    await engine.record_intent("p1", "ProductViewed", session_id="a")
    await engine.record_intent("p1", "ProductViewed", session_id="a")
    await engine.record_intent("p1", "ProductViewed", session_id="b")

    score = await engine.compute_score("p1")
    assert score["active_viewers"] == 2
    assert score["event_counts"] == {"ProductViewed": 3}


async def test_price_updates_are_published(fake_redis):
    pubsub = fake_redis.pubsub()
    channel = PricingEngine.PRICE_CHANNEL.format(product_id="p1")
    await pubsub.subscribe(channel)
    await pubsub.get_message(timeout=1)   # subscribe confirmation

    from decimal import Decimal
    await PricingEngine(fake_redis).broadcast_price_update("p1", Decimal("105.00"), "high", 15.0)

    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
    data = json.loads(message["data"])
    assert data["new_price"] == "105.00"
    assert data["demand_level"] == "high"
    await pubsub.aclose()
