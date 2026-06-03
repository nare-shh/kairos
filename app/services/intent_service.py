import logging
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.events.publisher import KafkaTopic, publish_event
from app.events.types import IntentEvent, ProductEvent
from app.models.event_store import EventStore
from app.models.product import Product
from app.schemas.intent import IntentScoreResponse, IntentTrackRequest
from app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)


class IntentService:
    """
    Handles user intent tracking and triggers the pricing engine.

    Two responsibilities:
    1. Record intent events (DB + Redis + Kafka)
    2. Re-score the product and apply new price if it changed
    """

    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self.redis = redis
        self.engine = PricingEngine(redis)

    async def track(self, data: IntentTrackRequest, user_id: str | None = None) -> dict:
        """
        Record a user intent event and trigger a pricing re-evaluation.

        Steps:
        1. Verify product exists
        2. Save to event_store (permanent record)
        3. Record in Redis (for scoring — fast, temporary)
        4. Publish to Kafka (for downstream consumers)
        5. Re-compute demand score
        6. Re-calculate price — if changed, update DB + broadcast
        """

        # 1. Verify product exists and is active
        result = await self.db.execute(
            select(Product).where(
                Product.id == data.product_id,
                Product.is_active == True,  # noqa: E712
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {data.product_id} not found",
            )

        product_id_str = str(data.product_id)

        # 2. Save to event_store — permanent, queryable audit record
        intent_event = EventStore(
            event_id=uuid.uuid4(),
            aggregate_type="intent",
            aggregate_id=product_id_str,
            event_type=data.event_type,
            payload={
                "product_id": product_id_str,
                "session_id": data.session_id,
                "metadata": data.metadata,
            },
            version=1,
            caused_by=user_id,
            metadata_={"source": "intent_api"},
        )
        self.db.add(intent_event)
        await self.db.flush()

        # 3. Record in Redis for the scoring window
        # This is fast in-memory storage — powers the live scoring
        await self.engine.record_intent(
            product_id=product_id_str,
            event_type=data.event_type,
            session_id=data.session_id,
        )

        # 4. Publish to Kafka — downstream services can react to intent
        await publish_event(
            topic=KafkaTopic.INTENT_EVENTS,
            event_type=data.event_type,
            aggregate_id=product_id_str,
            payload={
                "product_id": product_id_str,
                "event_type": data.event_type,
                "session_id": data.session_id,
            },
            caused_by=user_id,
        )

        # 5. Re-compute demand score from Redis window
        demand = await self.engine.compute_score(product_id_str)

        # 6. Calculate what the new price should be
        new_price = self.engine.calculate_price(
            base_price=product.base_price,
            min_price=product.min_price,
            max_price=product.max_price,
            stock_qty=product.stock_quantity,
            low_stock_threshold=product.low_stock_threshold,
            demand_score=demand,
        )

        price_changed = new_price != product.current_price

        if price_changed:
            old_price = product.current_price

            # Update the read model (products table)
            product.current_price = new_price

            # Save a ProductPriceChanged event — this is what makes the audit trail rich
            # Every dynamic price change is recorded with WHY it changed (demand data)
            price_event = EventStore(
                event_id=uuid.uuid4(),
                aggregate_type="product",
                aggregate_id=product_id_str,
                event_type=ProductEvent.PRICE_CHANGED,
                payload={
                    "old_price": str(old_price),
                    "new_price": str(new_price),
                    "trigger": "kairos_pricing_engine",    # ← automated, not human
                    "demand_score": demand["demand_score"],
                    "demand_level": demand["demand_level"],
                    "price_multiplier": demand["multiplier"],
                    "stock_qty": product.stock_quantity,
                    "triggering_event": data.event_type,   # what event caused this
                },
                version=1,
                caused_by="kairos_pricing_engine",
                metadata_={"automated": True},
            )
            self.db.add(price_event)
            await self.db.flush()

            # Broadcast to WebSocket subscribers — live price update
            await self.engine.broadcast_price_update(
                product_id=product_id_str,
                new_price=new_price,
                demand_level=demand["demand_level"],
                demand_score=demand["demand_score"],
            )

            logger.info(
                f"Price adjusted: {product.name} "
                f"{old_price} → {new_price} "
                f"(demand={demand['demand_level']}, score={demand['demand_score']})"
            )

        return {
            "tracked": True,
            "product_id": product_id_str,
            "event_type": data.event_type,
            "demand_level": demand["demand_level"],
            "demand_score": demand["demand_score"],
            "current_price": str(product.current_price),
            "price_changed": price_changed,
        }

    async def get_demand_score(self, product_id: uuid.UUID) -> IntentScoreResponse:
        """
        Return the current demand snapshot for a product.
        Used by the seller dashboard to see live demand signals.
        """
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        product_id_str = str(product_id)
        demand = await self.engine.compute_score(product_id_str)

        calculated_price = self.engine.calculate_price(
            base_price=product.base_price,
            min_price=product.min_price,
            max_price=product.max_price,
            stock_qty=product.stock_quantity,
            low_stock_threshold=product.low_stock_threshold,
            demand_score=demand,
        )

        from datetime import datetime, timezone
        return IntentScoreResponse(
            product_id=product_id,
            demand_score=demand["demand_score"],
            demand_level=demand["demand_level"],
            active_viewers=demand["active_viewers"],
            cart_adds_1h=demand["cart_adds_1h"],
            price_multiplier=demand["multiplier"],
            current_price=float(product.current_price),
            base_price=float(product.base_price),
            calculated_at=datetime.now(timezone.utc),
        )
