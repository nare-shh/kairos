"""
Stripe Webhook Handler
══════════════════════
Stripe calls this endpoint when a payment event occurs.

Security model:
───────────────
Anyone can POST to this endpoint.
But only Stripe knows the webhook signing secret.
We verify the signature on every request — if it doesn't match, we reject it.
This prevents attackers from faking payment success events.

Unsigned events are accepted ONLY in local mock-payment mode
(DEBUG=true and no real Stripe key) so the flow can be exercised with curl.

To test locally with real Stripe: use the Stripe CLI
    stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
"""

import json
import logging

import stripe
from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.db.redis import get_redis_or_none
from app.db.session import AsyncSessionLocal
from app.services.order_service import OrderService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

HANDLED_EVENTS = {
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
}


@router.post("/stripe", summary="Stripe payment webhook")
async def stripe_webhook(request: Request):
    """
    Receives Stripe webhook events.

    Handled events:
    - `payment_intent.succeeded`    → mark order as paid
    - `payment_intent.payment_failed` → mark as failed, restore stock

    All other events are acknowledged (200) but ignored.
    """
    # Read raw bytes — Stripe signs the raw body, not the parsed JSON
    # If we let FastAPI parse the body first, the signature check fails
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if settings.stripe_webhook_enabled:
        # Verify the webhook signature — proves the request came from Stripe
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.SignatureVerificationError:
            # Invalid signature → reject immediately
            logger.warning("Invalid Stripe webhook signature — request rejected")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature",
            )
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    elif settings.DEBUG and not settings.stripe_enabled:
        # Local mock-payment mode: no real money involved, accept unsigned JSON
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    else:
        # Real payments (or production) without a signing secret: refuse rather
        # than trust unsigned "payment succeeded" events
        logger.error("Stripe webhook received but STRIPE_WEBHOOK_SECRET is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook signing secret not configured",
        )

    # stripe.Event is dict-like, so the same access works in both modes
    event_type = event.get("type")
    event_data = event.get("data") or {}

    logger.info(f"Stripe webhook received: {event_type}")

    if event_type in HANDLED_EVENTS:
        # Use a fresh DB session for webhook processing
        # We can't use the request-scoped session here (webhooks come from Stripe, not users)
        async with AsyncSessionLocal() as db:
            try:
                service = OrderService(db, redis=get_redis_or_none())
                await service.handle_stripe_webhook(event_type, event_data)
                await db.commit()
                logger.info(f"Webhook {event_type} processed successfully")
            except Exception:
                await db.rollback()
                logger.exception(f"Webhook {event_type} processing failed")
                # Non-2xx → Stripe retries later. Safe: the handlers are idempotent.
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Webhook processing failed",
                )

    # Always return 200 to acknowledge receipt
    # Stripe will retry if it doesn't get a 2xx within 30 seconds
    return {"received": True, "event_type": event_type}
