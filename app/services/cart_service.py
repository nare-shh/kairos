"""
Cart Service — Redis-backed Shopping Cart
══════════════════════════════════════════

Why Redis for the cart (not PostgreSQL)?
────────────────────────────────────────
1. SPEED: Cart operations happen on every page interaction — must be sub-millisecond
2. TEMPORARY: Carts are abandoned 70% of the time — no need to permanently store them
3. TTL: Automatically expire abandoned carts after 7 days — no cleanup job needed
4. SIMPLICITY: A cart is just a key-value map. Redis HASH is perfect for this.

Cart structure in Redis:
   Key:   kairos:cart:{user_id}
   Value: Hash where field = product_id, value = JSON cart item

Example:
   kairos:cart:abc-123 → {
       "prod-456": '{"quantity": 2, "unit_price": "314.99", "product_name": "...", "sku": "..."}',
       "prod-789": '{"quantity": 1, "unit_price": "99.99",  "product_name": "...", "sku": "..."}',
   }
"""

import json
import uuid
from decimal import Decimal

import redis.asyncio as aioredis
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.cart import CartAddRequest, CartItemResponse, CartResponse, CartUpdateRequest

CART_KEY = "kairos:cart:{user_id}"
CART_TTL = 7 * 24 * 3600   # 7 days in seconds


class CartService:

    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self.redis = redis

    def _key(self, user_id: str) -> str:
        return CART_KEY.format(user_id=user_id)

    async def _get_active_product(self, product_id: uuid.UUID) -> Product:
        result = await self.db.execute(
            select(Product).where(
                Product.id == product_id,
                Product.is_active == True,  # noqa: E712
            )
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return product

    # ── Add item ───────────────────────────────────────────────────────────────
    async def add_item(self, user_id: str, data: CartAddRequest) -> CartResponse:
        """
        Add a product to the cart (or increase quantity if already there).

        We store the CURRENT dynamic price at the time of adding.
        The cart view always shows the live price next to it, and checkout
        charges the live price.
        """
        product = await self._get_active_product(data.product_id)

        if product.stock_quantity < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {product.stock_quantity}",
            )

        key = self._key(user_id)
        product_id_str = str(data.product_id)

        # Check if already in cart — if so, add quantities
        existing_raw = await self.redis.hget(key, product_id_str)
        if existing_raw:
            existing = json.loads(existing_raw)
            new_qty = existing["quantity"] + data.quantity
            if new_qty > product.stock_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot add {data.quantity} more. Cart already has "
                           f"{existing['quantity']}, only {product.stock_quantity} in stock.",
                )
            existing["quantity"] = new_qty
            existing["unit_price"] = str(product.current_price)   # refresh price
            item_data = existing
        else:
            item_data = {
                "quantity": data.quantity,
                "unit_price": str(product.current_price),   # dynamic price snapshot
                "product_name": product.name,
                "sku": product.sku,
            }

        # HSET: set a field in the Redis hash
        await self.redis.hset(key, product_id_str, json.dumps(item_data))
        # Reset TTL — user is active, extend the 7-day window
        await self.redis.expire(key, CART_TTL)

        return await self.get_cart(user_id)

    # ── Update quantity ────────────────────────────────────────────────────────
    async def update_item(self, user_id: str, data: CartUpdateRequest) -> CartResponse:
        """Update quantity. quantity=0 removes the item entirely."""
        key = self._key(user_id)
        product_id_str = str(data.product_id)

        if data.quantity == 0:
            # HDEL: remove a field from the Redis hash
            await self.redis.hdel(key, product_id_str)
        else:
            existing_raw = await self.redis.hget(key, product_id_str)
            if not existing_raw:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Item not found in cart",
                )
            product = await self._get_active_product(data.product_id)
            if data.quantity > product.stock_quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Only {product.stock_quantity} in stock",
                )
            item = json.loads(existing_raw)
            item["quantity"] = data.quantity
            await self.redis.hset(key, product_id_str, json.dumps(item))
            await self.redis.expire(key, CART_TTL)

        return await self.get_cart(user_id)

    # ── Get cart ───────────────────────────────────────────────────────────────
    async def get_cart(self, user_id: str) -> CartResponse:
        """
        Read the full cart and enrich it with LIVE product data from PostgreSQL:
        current Kairos price, stock, and availability (items may have been
        repriced, sold out or deactivated since they were added).
        """
        key = self._key(user_id)
        # HGETALL: get ALL fields and values from the Redis hash
        raw_items = await self.redis.hgetall(key)

        if not raw_items:
            return CartResponse(
                user_id=user_id,
                items=[],
                item_count=0,
                subtotal=Decimal("0.00"),
                is_empty=True,
            )

        # Fetch live product data for all cart items in ONE query (not N queries)
        products = await self._load_products(list(raw_items.keys()))

        items = []
        subtotal = Decimal("0.00")

        for product_id_str, item_raw in raw_items.items():
            item_data = json.loads(item_raw)
            qty = item_data["quantity"]
            added_price = Decimal(item_data["unit_price"])

            product = products.get(product_id_str)
            available = product is not None and product.is_active
            unit_price = product.current_price if available else added_price
            stock = product.stock_quantity if available else 0
            total = unit_price * qty
            subtotal += total

            items.append(CartItemResponse(
                product_id=product_id_str,
                product_name=product.name if product else item_data["product_name"],
                sku=product.sku if product else item_data["sku"],
                quantity=qty,
                unit_price=unit_price,
                added_unit_price=added_price,
                price_changed=unit_price != added_price,
                total_price=total,
                stock_available=stock,
                is_in_stock=available and stock >= qty,
            ))

        return CartResponse(
            user_id=user_id,
            items=items,
            item_count=sum(i.quantity for i in items),
            subtotal=subtotal,
            is_empty=False,
        )

    async def _load_products(self, product_ids: list[str]) -> dict[str, Product]:
        ids = []
        for product_id in product_ids:
            try:
                ids.append(uuid.UUID(product_id))
            except ValueError:
                continue
        if not ids:
            return {}
        result = await self.db.execute(select(Product).where(Product.id.in_(ids)))
        return {str(p.id): p for p in result.scalars().all()}

    # ── Clear cart ─────────────────────────────────────────────────────────────
    async def clear_cart(self, user_id: str) -> None:
        """Delete the entire cart — called after successful checkout."""
        await self.redis.delete(self._key(user_id))

    # ── Get raw cart items for checkout ───────────────────────────────────────
    async def get_raw_items(self, user_id: str) -> dict:
        """
        Returns the raw Redis hash for checkout processing.
        Returns empty dict if cart is empty.
        """
        key = self._key(user_id)
        raw = await self.redis.hgetall(key)
        return {k: json.loads(v) for k, v in raw.items()} if raw else {}
