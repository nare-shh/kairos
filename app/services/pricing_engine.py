"""
The Kairos Pricing Engine
═════════════════════════

This is the novel core of the project.

How it works:
─────────────
1. Every user interaction with a product generates an IntentEvent
2. Events are stored in Redis with a 1-hour TTL (sliding window)
3. When a new event arrives, we aggregate all events from the last hour
4. We compute a "demand score" by summing up event weights
5. The score maps to a price multiplier (higher demand → higher price)
6. We also apply a "stock pressure" modifier (low stock + high demand = surge)
7. new_price = base_price × demand_multiplier × stock_multiplier
8. Clamp to [min_price, max_price] — seller-defined safety bounds
9. If price changed → save event + broadcast via Redis pub/sub → WebSocket

This is conceptually identical to how Uber Surge Pricing works,
but applied to e-commerce with full event sourcing + audit trail.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

import redis.asyncio as aioredis

from app.events.types import IntentEvent

logger = logging.getLogger(__name__)


# ── Event Weights ─────────────────────────────────────────────────────────────
# These are the "votes" each action contributes to the demand score.
# Higher weight = stronger signal of purchase intent.
# Negative weights = signal that demand may be dropping.
#
# These values are tunable — in a real system, they'd be A/B tested
# and adjusted based on conversion data.

INTENT_WEIGHTS: dict[str, float] = {
    IntentEvent.PRODUCT_VIEWED: 1.0,          # passive interest
    IntentEvent.PRODUCT_SEARCH: 0.5,          # searching = mild intent
    IntentEvent.WISHLIST_ADDED: 2.0,          # "want this later" = real interest
    IntentEvent.CART_ADDED: 5.0,              # strong intent — they might buy
    IntentEvent.CART_REMOVED: -4.0,           # lost interest — reduce price pressure
    IntentEvent.CHECKOUT_STARTED: 8.0,        # very high intent
    IntentEvent.CHECKOUT_ABANDONED: -3.0,     # bailed — mild negative signal
    IntentEvent.PURCHASE_COMPLETED: 10.0,     # confirmed demand — strongest signal
}


# ── Demand Levels ─────────────────────────────────────────────────────────────
# Maps a score range to a human-readable label + price multiplier.
# Think of these as "gears" the pricing engine shifts between.

@dataclass
class DemandBand:
    label: str
    min_score: float
    max_score: float
    multiplier: float

# Ordered from lowest to highest demand
DEMAND_BANDS: list[DemandBand] = [
    DemandBand("low",    min_score=-999,  max_score=5,    multiplier=0.97),  # slight discount when cold
    DemandBand("medium", min_score=5,     max_score=15,   multiplier=1.00),  # base price
    DemandBand("high",   min_score=15,    max_score=35,   multiplier=1.05),  # +5%
    DemandBand("surge",  min_score=35,    max_score=999,  multiplier=1.12),  # +12% surge
]


# ── Stock Pressure Multipliers ────────────────────────────────────────────────
# When stock is low, scarcity increases value.
# This only kicks in when demand is already "high" or above.

def get_stock_multiplier(stock_qty: int, low_stock_threshold: int, demand_level: str) -> float:
    """
    Returns an additional multiplier based on stock scarcity.
    Only applies when demand is not 'low' — no surge on unpopular items.

    Examples:
    - 2 units left + surge demand   → +8% scarcity bonus
    - 5 units left + high demand    → +4% scarcity bonus
    - 50 units left                 → no bonus
    """
    if demand_level == "low":
        return 1.0   # don't apply scarcity to items nobody wants

    if stock_qty <= 0:
        return 1.0   # out of stock — pricing is irrelevant, handle separately

    # How "scarce" is this item? (0 = full, 1 = almost empty)
    scarcity_ratio = max(0.0, 1.0 - (stock_qty / max(low_stock_threshold, 1)))

    if scarcity_ratio >= 0.8:      # ≤20% of threshold remaining
        return 1.08
    elif scarcity_ratio >= 0.5:    # ≤50% of threshold remaining
        return 1.04
    elif scarcity_ratio >= 0.2:    # ≤80% of threshold remaining
        return 1.02
    else:
        return 1.0   # plenty in stock — no scarcity bonus


class PricingEngine:
    """
    Stateless pricing engine — all state comes from Redis and DB.
    Instantiate with a Redis client; no DB needed (we only read cached signals).
    """

    # Redis key templates
    # f-string pattern: "kairos:intent:{product_id}:{event_type}"
    INTENT_KEY = "kairos:intent:{product_id}"           # stores event list as JSON
    SCORE_KEY  = "kairos:score:{product_id}"            # cached score
    VIEWERS_KEY = "kairos:viewers:{product_id}"         # active viewer sessions
    PRICE_CHANNEL = "kairos:price_update:{product_id}"  # pub/sub channel

    # How long to keep intent events in Redis (sliding window)
    WINDOW_SECONDS = 3600   # 1 hour

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    # ── Record an intent event in Redis ───────────────────────────────────────
    async def record_intent(
        self,
        product_id: str,
        event_type: str,
        session_id: str | None = None,
    ) -> None:
        """
        Push an intent event into Redis.

        We use a Redis List (LPUSH) — efficient for appending recent events.
        Each entry is a JSON object: {"type": "CartAdded", "ts": 1700000000}

        EXPIRE refreshes the TTL every time a new event comes in.
        So a product with active demand always keeps its signal history.
        """
        key = self.INTENT_KEY.format(product_id=product_id)

        event_record = json.dumps({
            "type": event_type,
            "ts": datetime.now(timezone.utc).timestamp(),
            "session": session_id,
        })

        # LPUSH = push to the LEFT (head) of the list — newest first
        await self.redis.lpush(key, event_record)

        # Keep only the last 500 events — prevents unbounded memory growth
        await self.redis.ltrim(key, 0, 499)

        # Reset TTL — 1 hour of inactivity clears the signal
        await self.redis.expire(key, self.WINDOW_SECONDS)

        # Track active viewers in a separate set (for analytics)
        if session_id and event_type == IntentEvent.PRODUCT_VIEWED:
            viewers_key = self.VIEWERS_KEY.format(product_id=product_id)
            await self.redis.sadd(viewers_key, session_id)
            await self.redis.expire(viewers_key, 900)   # 15-minute viewer window

    # ── Compute demand score ───────────────────────────────────────────────────
    async def compute_score(self, product_id: str) -> dict:
        """
        Aggregate all recent intent events into a single demand score.

        Returns a dict with:
        - demand_score: float
        - demand_level: str (low/medium/high/surge)
        - multiplier: float
        - event_counts: breakdown by type
        - active_viewers: int
        """
        key = self.INTENT_KEY.format(product_id=product_id)
        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - self.WINDOW_SECONDS

        # LRANGE 0 -1 = get ALL elements from the list
        raw_events = await self.redis.lrange(key, 0, -1)

        # Aggregate scores, only counting events within the time window
        total_score: float = 0.0
        event_counts: dict[str, int] = {}
        cart_adds = 0

        for raw in raw_events:
            try:
                ev = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            # Skip events outside our time window
            if ev.get("ts", 0) < cutoff:
                continue

            ev_type = ev.get("type", "")
            weight = INTENT_WEIGHTS.get(ev_type, 0.0)
            total_score += weight

            event_counts[ev_type] = event_counts.get(ev_type, 0) + 1

            if ev_type == IntentEvent.CART_ADDED:
                cart_adds += 1

        # Map score to demand band
        band = DEMAND_BANDS[1]  # default: medium
        for b in DEMAND_BANDS:
            if b.min_score <= total_score < b.max_score:
                band = b
                break

        # Count active viewers
        viewers_key = self.VIEWERS_KEY.format(product_id=product_id)
        active_viewers = await self.redis.scard(viewers_key)

        return {
            "demand_score": round(total_score, 2),
            "demand_level": band.label,
            "multiplier": band.multiplier,
            "event_counts": event_counts,
            "active_viewers": int(active_viewers),
            "cart_adds_1h": cart_adds,
        }

    # ── Calculate new price ────────────────────────────────────────────────────
    def calculate_price(
        self,
        base_price: Decimal,
        min_price: Decimal,
        max_price: Decimal,
        stock_qty: int,
        low_stock_threshold: int,
        demand_score: dict,
    ) -> Decimal:
        """
        THE FORMULA:
            new_price = base_price × demand_multiplier × stock_multiplier
            clamped to [min_price, max_price]

        All arithmetic uses Python's Decimal for exact money math.
        No floats anywhere near prices!
        """
        demand_multiplier = Decimal(str(demand_score["multiplier"]))
        stock_mult = get_stock_multiplier(
            stock_qty,
            low_stock_threshold,
            demand_score["demand_level"],
        )
        stock_multiplier = Decimal(str(stock_mult))

        # Calculate raw price
        raw_price = base_price * demand_multiplier * stock_multiplier

        # Round to 2 decimal places using banker's rounding (ROUND_HALF_UP for money)
        raw_price = raw_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Hard clamp: never go below min or above max (seller-defined safety bounds)
        if raw_price < min_price:
            return min_price
        if raw_price > max_price:
            return max_price

        return raw_price

    # ── Broadcast price update via Redis pub/sub ───────────────────────────────
    async def broadcast_price_update(
        self,
        product_id: str,
        new_price: Decimal,
        demand_level: str,
        demand_score: float,
    ) -> None:
        """
        Publish a price update message to a Redis channel.

        WebSocket connections subscribe to this channel.
        When a message arrives here, it gets pushed to all connected browsers instantly.

        Redis pub/sub is perfect for this:
        - Publisher (pricing engine): sends message to channel
        - Subscriber (WebSocket handler): receives and forwards to browser
        - No polling — completely event-driven
        """
        channel = self.PRICE_CHANNEL.format(product_id=product_id)

        message = json.dumps({
            "product_id": product_id,
            "new_price": str(new_price),
            "demand_level": demand_level,
            "demand_score": demand_score,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        await self.redis.publish(channel, message)
        logger.debug(f"Broadcast price update for {product_id}: {new_price} ({demand_level})")
