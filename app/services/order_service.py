"""
Order Service
══════════════
Handles the full checkout flow:
  1. Validate cart items + stock (with row-level locking to prevent overselling)
  2. Create Order + OrderItems in DB
  3. Deduct stock (with event)
  4. Save OrderCreated event
  5. Create Stripe PaymentIntent
  6. Return client_secret to frontend
"""

import uuid
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from math import ceil

import stripe
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.events.publisher import KafkaTopic, publish_event
from app.events.types import OrderEvent, ProductEvent
from app.models.event_store import EventStore
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.order import (
    CheckoutRequest,
    CheckoutResponse,
    OrderListResponse,
    OrderResponse,
)
from app.services.cart_service import CartService

# Configure Stripe with our secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


def generate_order_number() -> str:
    """
    Generate a human-readable order number.
    Format: ORD-2025-A3F9B  (year + 5 random hex chars, uppercase)
    Random enough to avoid collisions, readable enough for customer support.
    """
    year = datetime.now(timezone.utc).year
    random_part = secrets.token_hex(3).upper()   # 6 hex chars
    return f"ORD-{year}-{random_part}"


class OrderService:

    def __init__(self, db: AsyncSession):
        self.db = db

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
        # Simple tax: 18% GST (India standard, adjust per your market)
        tax_rate = Decimal("0.18")
        tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"))
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

            order_item = OrderItem(
                order_id=order_id,
                product_id=product.id,
                product_name=product.name,          # snapshot
                product_sku=product.sku,            # snapshot
                quantity=qty,
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
            )
            self.db.add(order_item)

            # Deduct stock
            old_stock = product.stock_quantity
            product.stock_quantity -= qty

            # Save StockUpdated event for each item deducted
            self.db.add(EventStore(
                event_id=uuid.uuid4(),
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
                version=1,
                caused_by=str(user.id),
                metadata_={"automated": True, "trigger": "checkout"},
            ))

        # 7. Save OrderCreated event — the order now exists in our event log
        self.db.add(EventStore(
            event_id=uuid.uuid4(),
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
            version=1,
            caused_by=str(user.id),
        ))

        await self.db.flush()

        # 8. Create Stripe PaymentIntent
        # Amount must be in the SMALLEST currency unit
        # For INR: amount in paise (1 rupee = 100 paise)
        # For USD: amount in cents (1 dollar = 100 cents)
        amount_in_paise = int(total * 100)

        client_secret = ""
        payment_intent_id = f"pi_mock_{order_id}"   # fallback if Stripe not configured

        if settings.STRIPE_SECRET_KEY and not settings.STRIPE_SECRET_KEY.startswith("sk_test_placeholder"):
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount_in_paise,
                    currency="inr",
                    metadata={
                        "order_id": str(order_id),
                        "order_number": order_number,
                        "user_id": str(user.id),
                    },
                    # automatic_payment_methods: let Stripe decide which methods to show
                    automatic_payment_methods={"enabled": True},
                )
                client_secret = intent.client_secret
                payment_intent_id = intent.id

            except stripe.StripeError as e:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Payment provider error: {str(e)}",
                )
        else:
            # Dev mode: generate a fake client_secret so the flow still works
            client_secret = f"pi_mock_{order_id}_secret_dev"
            payment_intent_id = f"pi_mock_{order_id}"

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

        # Re-fetch the order with items eagerly loaded via selectinload
        # This is required in async SQLAlchemy — lazy loading is not allowed
        # selectinload runs a second query: SELECT * FROM order_items WHERE order_id = X
        from sqlalchemy.orm import selectinload
        refreshed = await self.db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
        )
        order = refreshed.scalar_one()

        return CheckoutResponse(
            order=OrderResponse.model_validate(order),
            client_secret=client_secret,
            payment_intent_id=payment_intent_id,
            amount_to_pay=total,
            currency="inr",
        )

    # ── HANDLE STRIPE WEBHOOK ─────────────────────────────────────────────────
    async def handle_stripe_webhook(self, event_type: str, event_data: dict) -> None:
        """
        Process Stripe webhook events.

        Stripe calls this endpoint when a payment succeeds or fails.
        We update the order status and record the event.

        Security: we verify the webhook signature BEFORE calling this method
        (done in the route handler). So by the time we're here, the event is authentic.
        """
        intent = event_data.get("object", {})
        payment_intent_id = intent.get("id")

        if not payment_intent_id:
            return

        # Find the order by Stripe payment intent ID
        result = await self.db.execute(
            select(Order).where(Order.stripe_payment_intent_id == payment_intent_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            return  # unknown order — might be from another system, ignore

        if event_type == "payment_intent.succeeded":
            old_status = order.status
            order.status = "paid"
            order.paid_at = datetime.now(timezone.utc)

            self.db.add(EventStore(
                event_id=uuid.uuid4(),
                aggregate_type="order",
                aggregate_id=str(order.id),
                event_type=OrderEvent.PAYMENT_RECEIVED,
                payload={
                    "payment_intent_id": payment_intent_id,
                    "amount": intent.get("amount"),
                    "currency": intent.get("currency"),
                    "old_status": old_status,
                    "new_status": "paid",
                },
                version=1,
                caused_by="stripe_webhook",
                metadata_={"automated": True, "stripe_event": event_type},
            ))

            await publish_event(
                topic=KafkaTopic.ORDER_EVENTS,
                event_type=OrderEvent.PAYMENT_RECEIVED,
                aggregate_id=str(order.id),
                payload={"order_number": order.order_number, "amount": str(order.total_amount)},
            )

        elif event_type == "payment_intent.payment_failed":
            order.status = "payment_failed"

            # Restore stock for each item since payment failed
            items_result = await self.db.execute(
                select(OrderItem).where(OrderItem.order_id == order.id)
            )
            order_items = items_result.scalars().all()

            for item in order_items:
                prod_result = await self.db.execute(
                    select(Product).where(Product.id == item.product_id).with_for_update()
                )
                product = prod_result.scalar_one_or_none()
                if product:
                    old_qty = product.stock_quantity
                    product.stock_quantity += item.quantity
                    self.db.add(EventStore(
                        event_id=uuid.uuid4(),
                        aggregate_type="product",
                        aggregate_id=str(product.id),
                        event_type=ProductEvent.STOCK_UPDATED,
                        payload={
                            "old_quantity": old_qty,
                            "new_quantity": product.stock_quantity,
                            "delta": item.quantity,
                            "reason": f"payment failed for order {order.order_number} — stock restored",
                        },
                        version=1,
                        caused_by="stripe_webhook",
                    ))

            self.db.add(EventStore(
                event_id=uuid.uuid4(),
                aggregate_type="order",
                aggregate_id=str(order.id),
                event_type=OrderEvent.CANCELLED,
                payload={
                    "payment_intent_id": payment_intent_id,
                    "reason": "payment_failed",
                    "failure_message": intent.get("last_payment_error", {}).get("message", ""),
                },
                version=1,
                caused_by="stripe_webhook",
                metadata_={"automated": True},
            ))

        await self.db.flush()

    # ── GET ORDERS ─────────────────────────────────────────────────────────────
    async def get_user_orders(
        self, user: User, page: int = 1, page_size: int = 10
    ) -> OrderListResponse:
        """Fetch all orders for a user, newest first."""
        from sqlalchemy import func
        from sqlalchemy.orm import selectinload

        count_result = await self.db.execute(
            select(func.count(Order.id)).where(Order.user_id == user.id)
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Order)
            .where(Order.user_id == user.id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        orders = result.scalars().all()

        return OrderListResponse(
            items=[OrderResponse.model_validate(o) for o in orders],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_order(self, order_id: uuid.UUID, user: User) -> OrderResponse:
        """Get a single order. Users can only see their own; admins see all."""
        from sqlalchemy.orm import selectinload

        query = select(Order).where(Order.id == order_id).options(selectinload(Order.items))
        if user.role != "admin":
            query = query.where(Order.user_id == user.id)

        result = await self.db.execute(query)
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return OrderResponse.model_validate(order)
