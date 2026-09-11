"""
WebSocket — Live Price Updates
═══════════════════════════════

How WebSockets differ from regular HTTP:
─────────────────────────────────────────
HTTP:      Client asks → Server answers → connection closes
WebSocket: Connection STAYS OPEN → Server can push data anytime

This is what enables live price updates:
1. Browser connects: ws://localhost:8000/ws/prices/{product_id}
2. Connection stays open (persistent)
3. When pricing engine changes a price → publishes to Redis channel
4. This handler is subscribed to that channel
5. Message arrives → instantly forwarded to the browser
6. Browser updates the price display — no page refresh needed

This is how Uber shows surge pricing in real-time on their map.
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select

from app.core.security import decode_token
from app.db.redis import get_redis
from app.db.session import AsyncSessionLocal
from app.models.product import Product
from app.models.user import User
from app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

HEARTBEAT_SECONDS = 25       # keeps proxies (Railway, nginx) from closing idle sockets
POLICY_VIOLATION = 1008      # WebSocket close code: "you're not allowed here"


async def _forward_updates(websocket: WebSocket, pubsub) -> None:
    """Push every price update from Redis to the browser; heartbeat when idle."""
    while True:
        # Blocks up to HEARTBEAT_SECONDS waiting for the pricing engine
        message = await pubsub.get_message(
            ignore_subscribe_messages=True,  # skip the "subscribe" confirmation
            timeout=HEARTBEAT_SECONDS,
        )
        if message is None:
            await websocket.send_json({"type": "heartbeat"})
            continue

        try:
            data = json.loads(message["data"])
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Failed to decode price update: {e}")
            continue

        # A price update arrived from the pricing engine — forward it
        await websocket.send_json({"type": "price_update", **data})


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    """
    Reading is the only reliable way to notice the client went away.
    (Previously the handler only noticed on the next send, so sockets for
    quiet products leaked a Redis subscription forever.)
    """
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return


async def _serve(websocket: WebSocket, pubsub) -> None:
    """Run forwarding and disconnect detection until either one finishes."""
    tasks = {
        asyncio.create_task(_forward_updates(websocket, pubsub)),
        asyncio.create_task(_wait_for_disconnect(websocket)),
    }
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                logger.info(f"WebSocket closed: {exc!r}")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _price_snapshot(product_id: uuid.UUID) -> dict:
    """
    The price + demand right now, sent on connect. Without it, a price change
    broadcast just before the client subscribed would be missed and the page
    would show a stale price until the next change.
    """
    async with AsyncSessionLocal() as db:
        product = (
            await db.execute(select(Product).where(Product.id == product_id))
        ).scalar_one_or_none()
    if not product:
        return {}
    demand = await PricingEngine(get_redis()).compute_score(str(product_id))
    return {
        "current_price": str(product.current_price),
        "demand_level": demand["demand_level"],
        "demand_score": demand["demand_score"],
    }


@router.websocket("/ws/prices/{product_id}")
async def price_websocket(websocket: WebSocket, product_id: uuid.UUID):
    """
    WebSocket endpoint for live price updates on a specific product.

    Connect with: ws://localhost:8000/ws/prices/{product_id}

    On connect the server sends {"type": "connected", "current_price", "demand_level", ...}.
    Then it pushes a message whenever the price changes:
    {
        "type": "price_update",
        "product_id": "...",
        "new_price": "324.99",
        "demand_level": "high",
        "demand_score": 22.5,
        "updated_at": "2025-01-01T12:00:00Z"
    }
    and {"type": "heartbeat"} every ~25s when nothing happens.
    """
    # Step 1: Accept the WebSocket connection (like a handshake)
    await websocket.accept()

    # Step 2: Subscribe to the Redis pub/sub channel for this product
    # pubsub() creates a subscriber object — separate from the main Redis connection
    pubsub = get_redis().pubsub()
    await pubsub.subscribe(PricingEngine.PRICE_CHANNEL.format(product_id=product_id))
    logger.info(f"WebSocket connected: client watching product {product_id}")

    try:
        # Step 3: Confirm + send the current price (read AFTER subscribing,
        # so no update can fall in between)
        await websocket.send_json({
            "type": "connected",
            "product_id": str(product_id),
            "message": "Subscribed to live price updates",
            **await _price_snapshot(product_id),
        })
        # Step 4: Forward updates until the client leaves
        await _serve(websocket, pubsub)
    except WebSocketDisconnect:
        pass
    finally:
        # Always clean up the subscription — even if an exception occurred
        await pubsub.aclose()
        logger.info(f"WebSocket cleanup done: product {product_id}")


async def _authenticate(token: str | None) -> User | None:
    """Validate an access token passed as ?token= (browsers can't set WS headers)."""
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = uuid.UUID(payload.get("sub", ""))
    except (JWTError, ValueError):
        return None

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    return user if user and user.is_active else None


async def _seller_channels(user: User) -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Product.id).where(
                Product.seller_id == user.id,
                Product.status != "deleted",
            )
        )
        return [PricingEngine.PRICE_CHANNEL.format(product_id=pid) for pid in result.scalars().all()]


@router.websocket("/ws/dashboard")
async def seller_dashboard_websocket(websocket: WebSocket):
    """
    Seller dashboard WebSocket — live price changes across the seller's whole catalog.

    Connect with: ws://localhost:8000/ws/dashboard?token=<access_token>
    Sellers receive updates for their own products; admins for every product.
    """
    user = await _authenticate(websocket.query_params.get("token"))
    if not user or user.role not in ("seller", "admin"):
        # Closing before accept() rejects the handshake
        await websocket.close(code=POLICY_VIOLATION)
        return

    await websocket.accept()
    pubsub = get_redis().pubsub()

    try:
        if user.role == "admin":
            await pubsub.psubscribe(PricingEngine.PRICE_CHANNEL.format(product_id="*"))
            watching = "all products"
        else:
            channels = await _seller_channels(user)
            # A pub/sub with zero subscriptions can't be read — use a private channel
            await pubsub.subscribe(*(channels or [f"kairos:dashboard:{user.id}"]))
            watching = f"{len(channels)} product(s)"

        await websocket.send_json({
            "type": "connected",
            "message": f"Kairos Seller Dashboard — live demand feed active ({watching})",
        })
        await _serve(websocket, pubsub)
    except WebSocketDisconnect:
        logger.info("Seller dashboard WebSocket disconnected")
    finally:
        await pubsub.aclose()
