import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.events.publisher import KafkaTopic, publish_event
from app.events.store import append_event
from app.models.product import Product
from app.models.user import User
from app.schemas.intent import IntentScoreResponse, IntentTrackRequest
from app.services.pricing_engine import PricingEngine
from app.services.repricing import broadcast, reprice_product

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
        4. Publish to Kafka (for downstream consumers, e.g. trending)
        5. Re-compute demand score + price — if changed, update DB + broadcast
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
        await append_event(
            self.db,
            aggregate_type="intent",
            aggregate_id=product_id_str,
            event_type=data.event_type,
            payload={
                "product_id": product_id_str,
                "session_id": data.session_id,
                "metadata": data.metadata,
            },
            caused_by=user_id,
            metadata={"source": "intent_api"},
        )

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

        # 5. Re-score + re-price; broadcast to WebSocket subscribers if it moved
        demand, change = await reprice_product(self.db, self.engine, product, trigger=data.event_type)
        if change:
            await broadcast(self.engine, change)

        return {
            "tracked": True,
            "product_id": product_id_str,
            "event_type": data.event_type,
            "demand_level": demand["demand_level"],
            "demand_score": demand["demand_score"],
            "current_price": str(product.current_price),
            "price_changed": change is not None,
        }

    async def get_demand_score(self, product_id: uuid.UUID, user: User) -> IntentScoreResponse:
        """
        Return the current demand snapshot for a product.
        Used by the seller dashboard — sellers only see their own products.
        """
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product or product.status == "deleted":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        if user.role != "admin" and product.seller_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view demand data for your own products",
            )

        demand = await self.engine.compute_score(str(product_id))

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
