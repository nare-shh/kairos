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

To test locally: use the Stripe CLI
    stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
"""

import logging

import stripe
from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.order_service import OrderService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


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

    # Verify the webhook signature
    # This proves the request came from Stripe, not an attacker
    if settings.STRIPE_WEBHOOK_SECRET and not settings.STRIPE_WEBHOOK_SECRET.startswith("whsec_placeholder"):
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
        except Exception as e:
            logger.error(f"Webhook parse error: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        # Dev mode: skip signature verification (no real Stripe key configured)
        import json
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    event_type = event.get("type") if isinstance(event, dict) else event.type
    event_data = event.get("data") if isinstance(event, dict) else event.data

    logger.info(f"Stripe webhook received: {event_type}")

    # Only process payment events we care about
    handled_events = {
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
    }

    if event_type in handled_events:
        # Use a fresh DB session for webhook processing
        # We can't use the request-scoped session here (webhooks come from Stripe, not users)
        async with AsyncSessionLocal() as db:
            try:
                service = OrderService(db)
                await service.handle_stripe_webhook(event_type, event_data)
                await db.commit()
                logger.info(f"Webhook {event_type} processed successfully")
            except Exception as e:
                await db.rollback()
                logger.error(f"Webhook processing failed: {e}")
                # Return 200 anyway — if we return 4xx/5xx, Stripe will retry
                # We don't want retries for permanent errors

    # Always return 200 to acknowledge receipt
    # Stripe will retry if it doesn't get a 2xx within 30 seconds
    return {"received": True, "event_type": event_type}
