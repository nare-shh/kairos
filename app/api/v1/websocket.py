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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from app.db.redis import get_redis
from app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/prices/{product_id}")
async def price_websocket(
    websocket: WebSocket,
    product_id: str,
):
    """
    WebSocket endpoint for live price updates on a specific product.

    Connect with: ws://localhost:8000/ws/prices/{product_id}

    The server will push a message whenever the price changes:
    {
        "product_id": "...",
        "new_price": "324.99",
        "demand_level": "high",
        "demand_score": 22.5,
        "updated_at": "2025-01-01T12:00:00Z"
    }
    """
    # Step 1: Accept the WebSocket connection (like a handshake)
    await websocket.accept()
    logger.info(f"WebSocket connected: client watching product {product_id}")

    redis = get_redis()

    # Step 2: Subscribe to the Redis pub/sub channel for this product
    # pubsub() creates a subscriber object — separate from the main Redis connection
    pubsub = redis.pubsub()
    channel = PricingEngine.PRICE_CHANNEL.format(product_id=product_id)
    await pubsub.subscribe(channel)

    try:
        # Step 3: Send an immediate confirmation message to the client
        await websocket.send_json({
            "type": "connected",
            "product_id": product_id,
            "message": "Subscribed to live price updates",
        })

        # Step 4: Loop — wait for messages, forward them to the browser
        while True:
            # Check if client disconnected (they closed the browser tab)
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break

            # get_message() is non-blocking — returns None if no message yet
            # timeout=0.1 means we wait up to 100ms for a message
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,  # skip the "subscribe" confirmation
                timeout=0.1,
            )

            if message and message.get("type") == "message":
                # A price update arrived from the pricing engine!
                try:
                    data = json.loads(message["data"])
                    # Forward directly to the connected browser
                    await websocket.send_json({
                        "type": "price_update",
                        **data,
                    })
                    logger.debug(f"Pushed price update to client: {data.get('new_price')}")
                except (json.JSONDecodeError, Exception) as e:
                    logger.error(f"Failed to forward price update: {e}")
            else:
                # No message right now — yield control so other tasks can run
                # Without this, the while loop would spin and block the event loop
                await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        # Client closed their browser/tab — normal, not an error
        logger.info(f"WebSocket disconnected: product {product_id}")
    except Exception as e:
        logger.error(f"WebSocket error for product {product_id}: {e}")
    finally:
        # Always clean up the subscription — even if an exception occurred
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.info(f"WebSocket cleanup done: product {product_id}")


@router.websocket("/ws/dashboard")
async def seller_dashboard_websocket(websocket: WebSocket):
    """
    Seller dashboard WebSocket — receives demand signals across ALL their products.
    A seller can watch their entire catalog's demand in real-time.
    """
    await websocket.accept()

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Kairos Seller Dashboard — live demand feed active",
        })

        # Keep the connection alive with periodic pings
        # In a full implementation, we'd subscribe to all seller's product channels
        while True:
            if websocket.client_state == WebSocketState.DISCONNECTED:
                break
            await asyncio.sleep(30)
            await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        logger.info("Seller dashboard WebSocket disconnected")
