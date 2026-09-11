import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.order import (
    CheckoutRequest,
    CheckoutResponse,
    OrderListResponse,
    OrderPaymentResponse,
    OrderResponse,
    OrderStatusUpdateRequest,
)
from app.services.auth_service import get_current_user, require_role
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
    7. Creates a **Stripe PaymentIntent** (mock intent when Stripe isn't configured)

    **Returns:**
    - `order`: the created order (status: `pending_payment`)
    - `client_secret`: pass this to **Stripe.js** on the frontend to complete payment
    - `amount_to_pay`: the exact amount Stripe will charge (including tax)
    - `mock_payment`: `true` → complete with `POST /orders/{id}/mock-payment`

    **After payment completes:** Stripe sends a webhook → order status becomes `paid`.
    """
    order_service = OrderService(db, redis)
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


# ─── GET /orders/all — Admin: every order ────────────────────────────────────
@router.get("/all", response_model=OrderListResponse, summary="List all orders (admin only)")
async def list_all_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None, description="Filter by order status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    return await OrderService(db).list_all_orders(page, page_size, status)


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


# ─── GET /orders/{id}/payment — Resume payment ───────────────────────────────
@router.get(
    "/{order_id}/payment",
    response_model=OrderPaymentResponse,
    summary="Get payment details for an unpaid order",
)
async def get_payment_details(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the Stripe client secret so an unpaid order can be paid later."""
    return await OrderService(db).get_payment_details(order_id, current_user)


# ─── POST /orders/{id}/cancel ────────────────────────────────────────────────
@router.post("/{order_id}/cancel", response_model=OrderResponse, summary="Cancel an unpaid order")
async def cancel_order(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Cancels a `pending_payment` order and returns its items to stock."""
    return await OrderService(db, redis).cancel_order(order_id, current_user)


# ─── POST /orders/{id}/mock-payment — Dev/demo payment ───────────────────────
@router.post(
    "/{order_id}/mock-payment",
    response_model=OrderResponse,
    summary="Complete payment without Stripe (dev/demo mode)",
)
async def mock_payment(
    order_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """
    Only works for orders created while Stripe was not configured
    (their payment intent id starts with `pi_mock_`).
    """
    return await OrderService(db, redis).confirm_mock_payment(order_id, current_user)


# ─── PATCH /orders/{id}/status — Admin fulfilment ────────────────────────────
@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Advance order fulfilment (admin only)",
)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Allowed: `paid → processing → shipped → delivered`."""
    return await OrderService(db).update_status(order_id, payload.status, current_user)
