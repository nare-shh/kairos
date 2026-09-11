"""
Order Service
══════════════
Handles the full order lifecycle:

Checkout:
  1. Validate cart items + stock (with row-level locking to prevent overselling)
  2. Create Order + OrderItems in DB
  3. Deduct stock (with event)
  4. Save OrderCreated event
  5. Create Stripe PaymentIntent (or a mock one when Stripe isn't configured)
  6. Return client_secret to frontend

After checkout:
  pending_payment → paid              (Stripe webhook, or mock payment in dev)
  pending_payment → payment_failed    (Stripe webhook — stock restored)
  pending_payment → cancelled         (customer/admin — stock restored)
  paid → processing → shipped → delivered   (admin fulfilment)

Every transition is idempotent and recorded in the event store.
"""

import asyncio
import logging
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import redis.asyncio as aioredis
import stripe
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.events.publisher import KafkaTopic, publish_event
from app.events.store import append_event
from app.events.types import IntentEvent, OrderEvent, ProductEvent
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    CheckoutRequest,
    CheckoutResponse,
    OrderListResponse,
    OrderPaymentResponse,
    OrderResponse,
)
from app.services.cart_service import CartService
from app.services.pricing_engine import PricingEngine

logger = logging.getLogger(__name__)

# Configure Stripe with our secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

# Simple tax: 18% GST (India standard, adjust per your market)
TAX_RATE = Decimal("0.18")
CURRENCY = "inr"
MOCK_INTENT_PREFIX = "pi_mock_"

# Fulfilment transitions an admin may apply once an order is paid
FULFILMENT_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "paid": ("processing",),
    "processing": ("shipped",),
    "shipped": ("delivered",),
}
FULFILMENT_EVENTS = {
    "processing": OrderEvent.CONFIRMED,
    "shipped": OrderEvent.SHIPPED,
    "delivered": OrderEvent.DELIVERED,
}


def generate_order_number() -> str:
    """
    Generate a human-readable order number.
    Format: ORD-2025-A3F9B6  (year + 6 random hex chars, uppercase)
    Random enough to avoid collisions, readable enough for customer support.
    """
    year = datetime.now(timezone.utc).year
    random_part = secrets.token_hex(3).upper()   # 6 hex chars
    return f"ORD-{year}-{random_part}"


def to_minor_units(amount: Decimal) -> int:
    """
    Stripe wants the SMALLEST currency unit.
    For INR: amount in paise (1 rupee = 100 paise) → ₹123.45 = 12345
    """
    return int((amount * 100).quantize(Decimal("1")))


def is_mock_intent(payment_intent_id: str | None) -> bool:
    return bool(payment_intent_id) and payment_intent_id.startswith(MOCK_INTENT_PREFIX)


class OrderService:

    def __init__(self, db: AsyncSession, redis: aioredis.Redis | None = None):
        self.db = db
        # Optional — used to feed purchases/abandonments back into the pricing engine
        self.redis = redis

    # ── CHECKOUT ──────────────────────────────────────────────────────────────
    async def checkout(
        self,
        user: User,
        data: CheckoutRequest,
        cart_service: CartService,
    ) -> CheckoutResponse:
        """
        The most critical method in the entire system.
        Every step must succeed or everything rolls back (transaction).

        Key engineering: SELECT ... FOR UPDATE
        ─────────────────────────────────────────
        When two users try to buy the last item simultaneously:
        - Without lock: both read stock=1, both deduct, stock goes to -1 (OVERSELL!)
        - With FOR UPDATE: the second query WAITS until the first transaction commits
          Then it sees stock=0 and rejects. Correct!

        This is called a "pessimistic lock" — assumes contention will happen.
        """
        # 1. Read cart
        raw_items = await cart_service.get_raw_items(str(user.id))
        if not raw_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your cart is empty",
            )

        # 2. Fetch and LOCK all products in a single query
        # with_for_update() adds "FOR UPDATE" to the SQL
        # This locks the rows until our transaction commits — prevents race conditions
        product_ids = [uuid.UUID(pid) for pid in raw_items.keys()]
        result = await self.db.execute(
            select(Product)
            .where(Product.id.in_(product_ids))
            .with_for_update()   # ← THE LOCK — prevents overselling
        )
        products = {str(p.id): p for p in result.scalars().all()}

        # 3. Validate every item
        order_items_data = []
        subtotal = Decimal("0.00")

        for product_id_str, cart_item in raw_items.items():
            product = products.get(product_id_str)
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Product {product_id_str} is no longer available",
                )
            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{product.name}' is no longer available for purchase",
                )

            qty = cart_item["quantity"]
            if product.stock_quantity < qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Insufficient stock for '{product.name}'. "
                        f"Requested: {qty}, Available: {product.stock_quantity}"
                    ),
                )

            # Use current_price (the dynamic Kairos price), not the stale cart price
            # This is important: price may have changed since item was added to cart
            unit_price = product.current_price
            total_price = unit_price * qty
            subtotal += total_price

            order_items_data.append({
                "product": product,
                "quantity": qty,
                "unit_price": unit_price,
                "total_price": total_price,
            })

        # 4. Calculate totals
        tax_amount = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
        shipping = Decimal("0.00")   # Free shipping for now
        total = subtotal + tax_amount + shipping

        # 5. Create order
        order_id = uuid.uuid4()
        order_number = generate_order_number()

        order = Order(
            id=order_id,
            order_number=order_number,
            user_id=user.id,
            status="pending_payment",
            subtotal=subtotal,
            tax_amount=tax_amount,
            shipping_amount=shipping,
            total_amount=total,
            shipping_address=data.shipping_address.model_dump(),
            notes=data.notes,
        )
        self.db.add(order)
        await self.db.flush()   # get the order ID

        # 6. Create order items + deduct stock
        for item_data in order_items_data:
            product = item_data["product"]
            qty = item_data["quantity"]

            self.db.add(OrderItem(
                order_id=order_id,
                product_id=product.id,
                product_name=product.name,          # snapshot
                product_sku=product.sku,            # snapshot
                quantity=qty,
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
            ))

            # Deduct stock
            old_stock = product.stock_quantity
            product.stock_quantity -= qty

            # Save StockUpdated event for each item deducted
            await append_event(
                self.db,
                aggregate_type="product",
                aggregate_id=str(product.id),
                event_type=ProductEvent.STOCK_UPDATED,
                payload={
                    "old_quantity": old_stock,
                    "new_quantity": product.stock_quantity,
                    "delta": -qty,
                    "reason": f"sold via order {order_number}",
                    "order_id": str(order_id),
                    "is_low_stock": product.stock_quantity <= product.low_stock_threshold,
                },
                caused_by=str(user.id),
                metadata={"automated": True, "trigger": "checkout"},
            )

        # 7. Save OrderCreated event — the order now exists in our event log
        await append_event(
            self.db,
            aggregate_type="order",
            aggregate_id=str(order_id),
            event_type=OrderEvent.CREATED,
            payload={
                "order_number": order_number,
                "user_id": str(user.id),
                "items": [
                    {
                        "product_id": str(i["product"].id),
                        "product_name": i["product"].name,
                        "quantity": i["quantity"],
                        "unit_price": str(i["unit_price"]),
                    }
                    for i in order_items_data
                ],
                "subtotal": str(subtotal),
                "tax": str(tax_amount),
                "total": str(total),
                "shipping_address": data.shipping_address.model_dump(),
            },
            caused_by=str(user.id),
        )

        # 8. Create the PaymentIntent
        if settings.stripe_enabled:
            try:
                # The Stripe SDK is synchronous — run it off the event loop
                intent = await asyncio.to_thread(
                    stripe.PaymentIntent.create,
                    amount=to_minor_units(total),
                    currency=CURRENCY,
                    metadata={
                        "order_id": str(order_id),
                        "order_number": order_number,
                        "user_id": str(user.id),
                    },
                    # automatic_payment_methods: let Stripe decide which methods to show
                    automatic_payment_methods={"enabled": True},
                )
            except stripe.StripeError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Payment provider error: {e.user_message or str(e)}",
                )
            client_secret = intent.client_secret
            payment_intent_id = intent.id
        else:
            # Dev mode: a mock intent — pay it with POST /orders/{id}/mock-payment
            payment_intent_id = f"{MOCK_INTENT_PREFIX}{order_id}"
            client_secret = f"{payment_intent_id}_secret_dev"

        # 9. Save Stripe IDs to the order
        order.stripe_payment_intent_id = payment_intent_id
        order.stripe_client_secret = client_secret

        # 10. Clear the cart — items are now committed to the order
        await cart_service.clear_cart(str(user.id))

        # 11. Publish to Kafka for downstream consumers
        await publish_event(
            topic=KafkaTopic.ORDER_EVENTS,
            event_type=OrderEvent.CREATED,
            aggregate_id=str(order_id),
            payload={"order_number": order_number, "total": str(total)},
            caused_by=str(user.id),
        )

        await self.db.flush()
        order = await self._load(order_id)

        return CheckoutResponse(
            order=OrderResponse.model_validate(order),
            client_secret=client_secret,
            payment_intent_id=payment_intent_id,
            amount_to_pay=total,
            currency=CURRENCY,
            mock_payment=is_mock_intent(payment_intent_id),
        )

    # ── HANDLE STRIPE WEBHOOK ─────────────────────────────────────────────────
    async def handle_stripe_webhook(self, event_type: str, event_data: dict) -> None:
        """
        Process Stripe webhook events.

        Stripe calls this endpoint when a payment succeeds or fails.
        We update the order status and record the event.

        Security: we verify the webhook signature BEFORE calling this method
        (done in the route handler). So by the time we're here, the event is authentic.

        Idempotency: Stripe delivers events at-least-once. Transitions only apply
        to orders still in pending_payment, so duplicates are harmless (previously a
        duplicate payment_failed event restored the stock twice).
        """
        intent = (event_data or {}).get("object") or {}
        payment_intent_id = intent.get("id")

        if not payment_intent_id:
            return

        # Find the order by Stripe payment intent ID — lock it so concurrent
        # deliveries of the same event are processed one after the other
        result = await self.db.execute(
            select(Order)
            .where(Order.stripe_payment_intent_id == payment_intent_id)
            .with_for_update()
        )
        order = result.scalar_one_or_none()
        if not order:
            return  # unknown order — might be from another system, ignore

        if event_type == "payment_intent.succeeded":
            await self._mark_paid(
                order,
                amount=intent.get("amount"),
                currency=intent.get("currency"),
                caused_by="stripe_webhook",
            )
        elif event_type == "payment_intent.payment_failed":
            error = intent.get("last_payment_error") or {}
            await self._fail_payment(order, failure_message=error.get("message", ""))

        await self.db.flush()

    # ── CUSTOMER ACTIONS ──────────────────────────────────────────────────────
    async def cancel_order(self, order_id: uuid.UUID, user: User) -> OrderResponse:
        """Cancel an unpaid order and give its stock back."""
        order = await self._get_order_for(order_id, user, for_update=True)
        if order.status != "pending_payment":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Only unpaid orders can be cancelled (this order is '{order.status}')",
            )

        if settings.stripe_enabled and not is_mock_intent(order.stripe_payment_intent_id):
            try:
                await asyncio.to_thread(stripe.PaymentIntent.cancel, order.stripe_payment_intent_id)
            except stripe.StripeError as e:
                # e.g. the customer already paid — never cancel an order Stripe charged
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Payment could not be cancelled: {e.user_message or str(e)}",
                )

        order.status = "cancelled"
        await self._restore_stock(
            order, reason=f"order {order.order_number} cancelled", caused_by=str(user.id)
        )
        await append_event(
            self.db,
            aggregate_type="order",
            aggregate_id=str(order.id),
            event_type=OrderEvent.CANCELLED,
            payload={
                "reason": "cancelled_by_customer" if order.user_id == user.id else "cancelled_by_admin",
                "old_status": "pending_payment",
                "new_status": "cancelled",
            },
            caused_by=str(user.id),
        )
        # Walking away from a checkout is a (mild) negative demand signal
        await self._record_demand_signal(order, IntentEvent.CHECKOUT_ABANDONED)
        await publish_event(
            topic=KafkaTopic.ORDER_EVENTS,
            event_type=OrderEvent.CANCELLED,
            aggregate_id=str(order.id),
            payload={"order_number": order.order_number, "reason": "cancelled"},
            caused_by=str(user.id),
        )

        await self.db.flush()
        return OrderResponse.model_validate(await self._load(order.id))

    async def confirm_mock_payment(self, order_id: uuid.UUID, user: User) -> OrderResponse:
        """
        Dev/demo only: complete payment for an order created without Stripe.
        Orders created with real Stripe keys can only be paid through Stripe.
        """
        order = await self._get_order_for(order_id, user, for_update=True)
        if not is_mock_intent(order.stripe_payment_intent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This order must be paid through Stripe",
            )
        if order.status != "pending_payment":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This order is not awaiting payment (status: '{order.status}')",
            )

        await self._mark_paid(
            order,
            amount=to_minor_units(order.total_amount),
            currency=CURRENCY,
            caused_by=str(user.id),
        )
        await self.db.flush()
        return OrderResponse.model_validate(await self._load(order.id))

    async def get_payment_details(self, order_id: uuid.UUID, user: User) -> OrderPaymentResponse:
        """Resume payment for an unpaid order (e.g. the customer closed the tab)."""
        order = await self._get_order_for(order_id, user)
        if order.status != "pending_payment":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This order is not awaiting payment (status: '{order.status}')",
            )
        return OrderPaymentResponse(
            order_id=order.id,
            client_secret=order.stripe_client_secret or "",
            payment_intent_id=order.stripe_payment_intent_id or "",
            amount_to_pay=order.total_amount,
            currency=CURRENCY,
            mock_payment=is_mock_intent(order.stripe_payment_intent_id),
        )

    # ── ADMIN FULFILMENT ──────────────────────────────────────────────────────
    async def update_status(self, order_id: uuid.UUID, new_status: str, admin: User) -> OrderResponse:
        result = await self.db.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if new_status not in FULFILMENT_TRANSITIONS.get(order.status, ()):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot move an order from '{order.status}' to '{new_status}'",
            )

        old_status = order.status
        order.status = new_status
        event_type = FULFILMENT_EVENTS[new_status]
        await append_event(
            self.db,
            aggregate_type="order",
            aggregate_id=str(order.id),
            event_type=event_type,
            payload={"old_status": old_status, "new_status": new_status},
            caused_by=str(admin.id),
        )
        await publish_event(
            topic=KafkaTopic.ORDER_EVENTS,
            event_type=event_type,
            aggregate_id=str(order.id),
            payload={"order_number": order.order_number, "status": new_status},
            caused_by=str(admin.id),
        )

        await self.db.flush()
        return OrderResponse.model_validate(await self._load(order.id))

    # ── GET ORDERS ─────────────────────────────────────────────────────────────
    async def get_user_orders(
        self, user: User, page: int = 1, page_size: int = 10
    ) -> OrderListResponse:
        """Fetch all orders for a user, newest first."""
        return await self._list(Order.user_id == user.id, page, page_size)

    async def list_all_orders(
        self, page: int = 1, page_size: int = 20, status_filter: str | None = None
    ) -> OrderListResponse:
        """Admin: every order, optionally filtered by status."""
        condition = Order.status == status_filter if status_filter else None
        return await self._list(condition, page, page_size)

    async def get_order(self, order_id: uuid.UUID, user: User) -> OrderResponse:
        """Get a single order. Users can only see their own; admins see all."""
        order = await self._get_order_for(order_id, user)
        return OrderResponse.model_validate(await self._load(order.id))

    # ── Private: state transitions ────────────────────────────────────────────
    async def _mark_paid(self, order: Order, *, amount, currency, caused_by: str) -> bool:
        if order.status != "pending_payment":
            logger.info(f"Order {order.order_number} is already '{order.status}' — payment event ignored")
            return False

        old_status = order.status
        order.status = "paid"
        order.paid_at = datetime.now(timezone.utc)

        await append_event(
            self.db,
            aggregate_type="order",
            aggregate_id=str(order.id),
            event_type=OrderEvent.PAYMENT_RECEIVED,
            payload={
                "payment_intent_id": order.stripe_payment_intent_id,
                "amount": amount,
                "currency": currency,
                "old_status": old_status,
                "new_status": "paid",
            },
            caused_by=caused_by,
            metadata={"automated": caused_by == "stripe_webhook"},
        )

        # A confirmed purchase is the strongest demand signal there is
        await self._record_demand_signal(order, IntentEvent.PURCHASE_COMPLETED)

        await publish_event(
            topic=KafkaTopic.ORDER_EVENTS,
            event_type=OrderEvent.PAYMENT_RECEIVED,
            aggregate_id=str(order.id),
            payload={"order_number": order.order_number, "amount": str(order.total_amount)},
        )
        return True

    async def _fail_payment(self, order: Order, failure_message: str) -> bool:
        if order.status != "pending_payment":
            logger.info(f"Order {order.order_number} is already '{order.status}' — failure event ignored")
            return False

        order.status = "payment_failed"

        # Restore stock for each item since payment failed
        await self._restore_stock(
            order,
            reason=f"payment failed for order {order.order_number} — stock restored",
            caused_by="stripe_webhook",
        )
        await append_event(
            self.db,
            aggregate_type="order",
            aggregate_id=str(order.id),
            event_type=OrderEvent.CANCELLED,
            payload={
                "payment_intent_id": order.stripe_payment_intent_id,
                "reason": "payment_failed",
                "failure_message": failure_message,
            },
            caused_by="stripe_webhook",
            metadata={"automated": True},
        )
        await publish_event(
            topic=KafkaTopic.ORDER_EVENTS,
            event_type=OrderEvent.CANCELLED,
            aggregate_id=str(order.id),
            payload={"order_number": order.order_number, "reason": "payment_failed"},
        )
        return True

    async def _restore_stock(self, order: Order, reason: str, caused_by: str) -> None:
        for item in await self._items(order.id):
            result = await self.db.execute(
                select(Product).where(Product.id == item.product_id).with_for_update()
            )
            product = result.scalar_one_or_none()
            if not product:
                continue
            old_qty = product.stock_quantity
            product.stock_quantity += item.quantity
            await append_event(
                self.db,
                aggregate_type="product",
                aggregate_id=str(product.id),
                event_type=ProductEvent.STOCK_UPDATED,
                payload={
                    "old_quantity": old_qty,
                    "new_quantity": product.stock_quantity,
                    "delta": item.quantity,
                    "reason": reason,
                    "order_id": str(order.id),
                },
                caused_by=caused_by,
                metadata={"automated": True},
            )

    async def _record_demand_signal(self, order: Order, event_type: str) -> None:
        """Best effort: feed order outcomes into the pricing engine's Redis window."""
        if self.redis is None:
            return
        engine = PricingEngine(self.redis)
        for item in await self._items(order.id):
            try:
                await engine.record_intent(str(item.product_id), event_type)
            except Exception as e:
                logger.warning(f"Could not record {event_type} signal for {item.product_id}: {e}")

    # ── Private: queries ──────────────────────────────────────────────────────
    async def _items(self, order_id: uuid.UUID) -> list[OrderItem]:
        result = await self.db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        return list(result.scalars().all())

    async def _load(self, order_id: uuid.UUID) -> Order:
        """
        Re-fetch an order with items eagerly loaded via selectinload.
        Required in async SQLAlchemy — lazy loading is not allowed.
        """
        result = await self.db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def _get_order_for(
        self, order_id: uuid.UUID, user: User, for_update: bool = False
    ) -> Order:
        """Users can only reach their own orders; admins reach all (404 otherwise)."""
        query = select(Order).where(Order.id == order_id)
        if user.role != "admin":
            query = query.where(Order.user_id == user.id)
        if for_update:
            query = query.with_for_update()
        order = (await self.db.execute(query)).scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order

    async def _list(self, condition, page: int, page_size: int) -> OrderListResponse:
        count_query = select(func.count(Order.id))
        query = select(Order).options(selectinload(Order.items))
        if condition is not None:
            count_query = count_query.where(condition)
            query = query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()
        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(Order.created_at.desc()).offset(offset).limit(page_size)
        )
        return OrderListResponse(
            items=[OrderResponse.model_validate(o) for o in result.scalars().all()],
            total=total,
            page=page,
            page_size=page_size,
        )
