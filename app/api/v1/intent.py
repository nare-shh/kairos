import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.intent import IntentScoreResponse, IntentTrackRequest
from app.services.auth_service import get_current_user, require_role
from app.services.intent_service import IntentService

router = APIRouter(prefix="/intent", tags=["Intent & Pricing"])


# ─── POST /intent/track — Record a user behavior event ───────────────────────
@router.post(
    "/track",
    summary="Track a user intent event",
)
async def track_intent(
    payload: IntentTrackRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    # Optional auth — anonymous users can also generate intent events
    # We use a try/except approach via Optional dependency
):
    """
    Record a user interaction with a product.

    This is the input to the Kairos pricing engine.
    Call this endpoint every time a user:
    - Views a product page (`ProductViewed`)
    - Adds to cart (`CartAdded`)
    - Removes from cart (`CartRemoved`)
    - Adds to wishlist (`WishlistAdded`)
    - Starts checkout (`CheckoutStarted`)
    - Abandons checkout (`CheckoutAbandoned`)
    - Completes purchase (`PurchaseCompleted`)

    The pricing engine will immediately re-score the product and
    adjust the current price if demand thresholds are crossed.
    """
    service = IntentService(db, redis)
    # No auth required — anonymous browsing still generates intent signals
    return await service.track(payload, user_id=None)


# ─── POST /intent/track (authenticated) ──────────────────────────────────────
@router.post(
    "/track/authenticated",
    summary="Track intent event (authenticated user)",
)
async def track_intent_authenticated(
    payload: IntentTrackRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """
    Same as /track but requires authentication.
    Authenticated events have higher signal quality (tied to a real user).
    """
    service = IntentService(db, redis)
    return await service.track(payload, user_id=str(current_user.id))


# ─── GET /intent/score/{product_id} — Current demand state ───────────────────
@router.get(
    "/score/{product_id}",
    response_model=IntentScoreResponse,
    summary="Get current demand score for a product",
)
async def get_demand_score(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    # Sellers and admins only — this exposes sensitive demand data
    current_user: User = Depends(require_role("seller", "admin")),
):
    """
    **Seller Dashboard endpoint.**

    Returns the current demand intelligence for a product:
    - `demand_score`: aggregated weighted score (last 1 hour)
    - `demand_level`: `low` | `medium` | `high` | `surge`
    - `active_viewers`: unique sessions currently viewing (last 15 min)
    - `cart_adds_1h`: how many times added to cart in the last hour
    - `price_multiplier`: the multiplier currently applied to base price
    - `current_price`: what buyers see right now
    - `base_price`: what the seller originally set
    """
    service = IntentService(db, redis)
    return await service.get_demand_score(product_id)
