import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.order import CheckoutRequest, CheckoutResponse, OrderListResponse, OrderResponse
from app.services.auth_service import get_current_user
from app.services.cart_service import CartService
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])


# ─── POST /orders/checkout ────────────────────────────────────────────────────
@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Checkout — create order from cart",
)
async def checkout(
    payload: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """
    Convert the current cart into an order and create a Stripe payment.

    **Flow:**
    1. Validates all cart items (stock, availability)
    2. Locks product rows (prevents overselling under concurrency)
    3. Deducts stock
    4. Creates `Order` + `OrderItems` in DB
    5. Saves `OrderCreated` event to event store
    6. Clears the cart
    7. Creates a **Stripe PaymentIntent**

    **Returns:**
    - `order`: the created order (status: `pending_payment`)
    - `client_secret`: pass this to **Stripe.js** on the frontend to complete payment
    - `amount_to_pay`: the exact amount Stripe will charge (including tax)

    **After payment completes:** Stripe sends a webhook → order status becomes `paid`.
    """
    order_service = OrderService(db)
    cart_service = CartService(db, redis)
    return await order_service.checkout(current_user, payload, cart_service)


# ─── GET /orders — List user's orders ────────────────────────────────────────
@router.get("", response_model=OrderListResponse, summary="List your orders")
async def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all orders placed by the authenticated user, newest first."""
    service = OrderService(db)
    return await service.get_user_orders(current_user, page, page_size)


# ─── GET /orders/{id} — Get single order ──────────────────────────────────────
@router.get("/{order_id}", response_model=OrderResponse, summary="Get order details")
async def get_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch a specific order with all its items.
    Users can only access their own orders. Admins can access any order.
    """
    service = OrderService(db)
    return await service.get_order(order_id, current_user)
