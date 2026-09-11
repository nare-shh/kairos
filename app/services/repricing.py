"""
Repricing — applies a PricingEngine decision to a product and records WHY.

Shared by:
- IntentService → reprices immediately when a new demand signal arrives
- Repricer loop → periodically reprices products whose demand window decayed
                  (signals expire after 1 hour, so prices must drift back even
                   when nobody is interacting with the product)
"""

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.events.store import append_event
from app.events.types import ProductEvent
from app.models.product import Product
from app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

# caused_by value for automated price changes — the frontend labels these "⚡ Kairos"
PRICING_ENGINE_ACTOR = "kairos_pricing_engine"


@dataclass
class PriceChange:
    product_id: str
    old_price: Decimal
    new_price: Decimal
    demand_level: str
    demand_score: float


async def reprice_product(
    db: AsyncSession,
    engine: PricingEngine,
    product: Product,
    trigger: str,
) -> tuple[dict, PriceChange | None]:
    """
    Re-score a product and update current_price if the engine's answer changed.

    Returns (demand snapshot, PriceChange or None).
    Does NOT broadcast — callers decide when (e.g. after commit).
    """
    product_id = str(product.id)
    demand = await engine.compute_score(product_id)

    new_price = engine.calculate_price(
        base_price=product.base_price,
        min_price=product.min_price,
        max_price=product.max_price,
        stock_qty=product.stock_quantity,
        low_stock_threshold=product.low_stock_threshold,
        demand_score=demand,
    )

    if new_price == product.current_price:
        return demand, None

    old_price = product.current_price
    product.current_price = new_price   # update the read model

    # Every dynamic price change is recorded with the demand data that caused it
    await append_event(
        db,
        aggregate_type="product",
        aggregate_id=product_id,
        event_type=ProductEvent.PRICE_CHANGED,
        payload={
            "old_price": str(old_price),
            "new_price": str(new_price),
            "trigger": PRICING_ENGINE_ACTOR,        # ← automated, not human
            "demand_score": demand["demand_score"],
            "demand_level": demand["demand_level"],
            "price_multiplier": demand["multiplier"],
            "stock_qty": product.stock_quantity,
            "triggering_event": trigger,            # what caused the re-evaluation
        },
        caused_by=PRICING_ENGINE_ACTOR,
        metadata={"automated": True},
    )

    logger.info(
        # ASCII only: Windows consoles (cp1252) can't encode "→" in log output
        f"Price adjusted: {product.name} {old_price} -> {new_price} "
        f"(demand={demand['demand_level']}, score={demand['demand_score']}, trigger={trigger})"
    )

    return demand, PriceChange(
        product_id=product_id,
        old_price=old_price,
        new_price=new_price,
        demand_level=demand["demand_level"],
        demand_score=demand["demand_score"],
    )


async def broadcast(engine: PricingEngine, change: PriceChange) -> None:
    """Push a price change to WebSocket subscribers via Redis pub/sub."""
    await engine.broadcast_price_update(
        product_id=change.product_id,
        new_price=change.new_price,
        demand_level=change.demand_level,
        demand_score=change.demand_score,
    )
