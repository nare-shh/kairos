"""
API integration tests — real PostgreSQL (migrated with Alembic), in-memory Redis.
Skipped automatically when PostgreSQL isn't reachable (see conftest.py).
"""

import uuid
from decimal import Decimal

from app.consumers.trending import apply_intent_event
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.pricing_engine import PricingEngine
from app.services.repricer import run_reprice_cycle

API = "/api/v1"
PASSWORD = "Password1"
ADDRESS = {
    "full_name": "Test Buyer",
    "line1": "42 MG Road",
    "city": "Chennai",
    "state": "Tamil Nadu",
    "postal_code": "600001",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def user_headers(client, email: str, role: str = "customer") -> dict:
    r = await client.post(f"{API}/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": "Test User", "role": role,
    })
    assert r.status_code == 201, r.text
    return await login(client, email)


async def login(client, email: str) -> dict:
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def admin_headers(client) -> dict:
    # Admins can't self-register — create one directly, like `python -m app.seed create-admin`
    async with AsyncSessionLocal() as db:
        db.add(User(
            id=uuid.uuid4(), email="admin@kairos.dev", full_name="Admin",
            hashed_password=hash_password(PASSWORD), role="admin",
        ))
        await db.commit()
    return await login(client, "admin@kairos.dev")


async def create_product(client, headers: dict, **overrides) -> dict:
    body = {
        "name": "Test Headphones",
        "sku": f"TST-{uuid.uuid4().hex[:6]}",
        "base_price": "100.00",
        "min_price": "80.00",
        "max_price": "130.00",
        "stock_quantity": 50,
        "low_stock_threshold": 10,
    }
    body.update(overrides)
    r = await client.post(f"{API}/products", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def track(client, product_id: str, event_type: str, session: str = "sess-1"):
    return await client.post(f"{API}/intent/track", json={
        "product_id": product_id, "event_type": event_type, "session_id": session,
    })


async def product_price(client, product_id: str) -> Decimal:
    r = await client.get(f"{API}/products/{product_id}")
    assert r.status_code == 200, r.text
    return Decimal(r.json()["current_price"])


async def product_stock(client, product_id: str) -> int:
    r = await client.get(f"{API}/products/{product_id}")
    assert r.status_code == 200, r.text
    return r.json()["stock_quantity"]


async def checkout(client, headers: dict, product_id: str, quantity: int) -> dict:
    r = await client.post(f"{API}/cart", json={"product_id": product_id, "quantity": quantity}, headers=headers)
    assert r.status_code == 200, r.text
    r = await client.post(f"{API}/orders/checkout", json={"shipping_address": ADDRESS}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ── System & Auth ─────────────────────────────────────────────────────────────

async def test_health_reports_dependencies(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_register_login_and_me(client):
    headers = await user_headers(client, "alice@kairos.dev")
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alice@kairos.dev"
    assert me.json()["role"] == "customer"

    duplicate = await client.post(f"{API}/auth/register", json={
        "email": "alice@kairos.dev", "password": PASSWORD,
    })
    assert duplicate.status_code == 409


async def test_admin_role_cannot_self_register(client):
    r = await client.post(f"{API}/auth/register", json={
        "email": "sneaky@kairos.dev", "password": PASSWORD, "role": "admin",
    })
    assert r.status_code == 422


# ── Products ──────────────────────────────────────────────────────────────────

async def test_customer_cannot_create_product(client):
    headers = await user_headers(client, "bob@kairos.dev")
    r = await client.post(f"{API}/products", json={
        "name": "Nope", "sku": "NOPE-1", "base_price": "10", "min_price": "5", "max_price": "20",
    }, headers=headers)
    assert r.status_code == 403


async def test_product_lifecycle(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    product = await create_product(client, seller)
    pid = product["id"]

    listing = (await client.get(f"{API}/products")).json()
    assert pid in [p["id"] for p in listing["items"]]

    # Bounds must keep min ≤ base ≤ max
    bad = await client.patch(f"{API}/products/{pid}", json={"min_price": "120.00"}, headers=seller)
    assert bad.status_code == 400

    ok = await client.patch(f"{API}/products/{pid}", json={
        "max_price": "150.00", "description": "Now with ANC",
    }, headers=seller)
    assert ok.status_code == 200
    assert Decimal(ok.json()["max_price"]) == Decimal("150.00")

    price = await client.put(f"{API}/products/{pid}/price", json={
        "new_base_price": "110.00", "reason": "Supplier cost increase",
    }, headers=seller)
    assert Decimal(price.json()["base_price"]) == Decimal("110.00")

    stock = await client.patch(f"{API}/products/{pid}/stock", json={
        "quantity_delta": -5, "reason": "damaged",
    }, headers=seller)
    assert stock.json()["stock_quantity"] == 45

    # Deactivated products disappear from the store but stay in the seller's catalog
    r = await client.post(f"{API}/products/{pid}/deactivate", headers=seller)
    assert r.json()["is_active"] is False
    assert (await client.get(f"{API}/products/{pid}")).status_code == 404
    mine = (await client.get(f"{API}/products/mine", headers=seller)).json()
    assert [p["status"] for p in mine["items"]] == ["inactive"]

    r = await client.post(f"{API}/products/{pid}/activate", headers=seller)
    assert r.json()["is_active"] is True
    assert (await client.get(f"{API}/products/{pid}")).status_code == 200

    assert (await client.delete(f"{API}/products/{pid}", headers=seller)).status_code == 204
    assert (await client.get(f"{API}/products/mine", headers=seller)).json()["items"] == []
    assert (await client.get(f"{API}/products/{pid}")).status_code == 404

    # The audit trail survives deletion and its versions are gap-free
    events = (await client.get(f"{API}/products/{pid}/events", headers=seller)).json()
    assert [e["version"] for e in events] == list(range(1, len(events) + 1))
    assert events[0]["event_type"] == "ProductCreated"
    assert events[-1]["event_type"] == "ProductDeleted"


async def test_sellers_cannot_touch_each_others_products(client):
    owner = await user_headers(client, "owner@kairos.dev", "seller")
    other = await user_headers(client, "other@kairos.dev", "seller")
    pid = (await create_product(client, owner))["id"]

    assert (await client.patch(f"{API}/products/{pid}", json={"name": "Mine now"}, headers=other)).status_code == 403
    assert (await client.get(f"{API}/intent/score/{pid}", headers=other)).status_code == 403
    assert (await client.get(f"{API}/products/{pid}/events", headers=other)).status_code == 403


# ── Pricing engine through the API ────────────────────────────────────────────

async def test_demand_signals_move_the_price(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    pid = (await create_product(client, seller))["id"]

    # 3 × CartAdded = score 15 → "high" band → ×1.05
    for _ in range(3):
        r = await track(client, pid, "CartAdded")
        assert r.status_code == 200, r.text
    assert r.json()["price_changed"] is True
    assert r.json()["demand_level"] == "high"
    assert await product_price(client, pid) == Decimal("105.00")

    history = (await client.get(f"{API}/products/{pid}/price-history")).json()
    assert history[0]["kind"] == "dynamic"
    assert Decimal(history[0]["new_price"]) == Decimal("105.00")
    assert history[0]["demand_level"] == "high"

    score = (await client.get(f"{API}/intent/score/{pid}", headers=seller)).json()
    assert score["demand_score"] == 15.0
    assert score["cart_adds_1h"] == 3

    # Purchases can only be recorded by the server
    assert (await track(client, pid, "PurchaseCompleted")).status_code == 422


async def test_repricer_lets_surge_prices_decay(client, fake_redis):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    pid = (await create_product(client, seller))["id"]
    for _ in range(3):
        await track(client, pid, "CartAdded")
    assert await product_price(client, pid) == Decimal("105.00")

    # Simulate the 1-hour signal window expiring
    await fake_redis.delete(PricingEngine.INTENT_KEY.format(product_id=pid))

    assert await run_reprice_cycle(fake_redis) == 1
    # No signals → "low" band → ×0.97
    assert await product_price(client, pid) == Decimal("97.00")
    assert await run_reprice_cycle(fake_redis) == 0   # stable afterwards


async def test_trending_products(client, fake_redis):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    hot = (await create_product(client, seller, name="Hot Item"))["id"]
    warm = (await create_product(client, seller, name="Warm Item"))["id"]

    await apply_intent_event(fake_redis, {"aggregate_id": hot, "event_type": "CartAdded"})
    await apply_intent_event(fake_redis, {"aggregate_id": warm, "event_type": "ProductViewed"})

    trending = (await client.get(f"{API}/products/trending")).json()
    assert [p["id"] for p in trending] == [hot, warm]

    await client.post(f"{API}/products/{hot}/deactivate", headers=seller)
    trending = (await client.get(f"{API}/products/trending")).json()
    assert [p["id"] for p in trending] == [warm]


# ── Cart ──────────────────────────────────────────────────────────────────────

async def test_cart_shows_the_live_price(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    pid = (await create_product(client, seller))["id"]

    await client.post(f"{API}/cart", json={"product_id": pid, "quantity": 1}, headers=buyer)
    for _ in range(3):
        await track(client, pid, "CartAdded")   # price → 105.00

    item = (await client.get(f"{API}/cart", headers=buyer)).json()["items"][0]
    assert Decimal(item["unit_price"]) == Decimal("105.00")
    assert Decimal(item["added_unit_price"]) == Decimal("100.00")
    assert item["price_changed"] is True

    too_many = await client.patch(f"{API}/cart", json={"product_id": pid, "quantity": 99}, headers=buyer)
    assert too_many.status_code == 400


# ── Orders & payments ─────────────────────────────────────────────────────────

async def test_checkout_and_mock_payment(client, fake_redis):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    pid = (await create_product(client, seller, stock_quantity=10))["id"]

    result = await checkout(client, buyer, pid, 2)
    order = result["order"]
    assert result["mock_payment"] is True
    assert order["status"] == "pending_payment"
    assert Decimal(result["amount_to_pay"]) == Decimal("236.00")   # 2 × 100 + 18% GST
    assert await product_stock(client, pid) == 8
    assert (await client.get(f"{API}/cart", headers=buyer)).json()["is_empty"] is True

    paid = await client.post(f"{API}/orders/{order['id']}/mock-payment", headers=buyer)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_at"] is not None

    again = await client.post(f"{API}/orders/{order['id']}/mock-payment", headers=buyer)
    assert again.status_code == 409

    # The purchase fed the pricing engine
    signals = await fake_redis.lrange(PricingEngine.INTENT_KEY.format(product_id=pid), 0, -1)
    assert any("PurchaseCompleted" in s for s in signals)

    orders = (await client.get(f"{API}/orders", headers=buyer)).json()
    assert orders["total"] == 1


async def test_checkout_rejects_insufficient_stock(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    pid = (await create_product(client, seller, stock_quantity=2))["id"]

    await client.post(f"{API}/cart", json={"product_id": pid, "quantity": 2}, headers=buyer)
    await client.patch(f"{API}/products/{pid}/stock", json={"quantity_delta": -1, "reason": "sold offline"}, headers=seller)

    r = await client.post(f"{API}/orders/checkout", json={"shipping_address": ADDRESS}, headers=buyer)
    assert r.status_code == 400
    assert "Insufficient stock" in r.json()["detail"]


async def test_cancel_restores_stock(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    pid = (await create_product(client, seller, stock_quantity=10))["id"]

    order = (await checkout(client, buyer, pid, 3))["order"]
    assert await product_stock(client, pid) == 7

    r = await client.post(f"{API}/orders/{order['id']}/cancel", headers=buyer)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert await product_stock(client, pid) == 10

    assert (await client.post(f"{API}/orders/{order['id']}/cancel", headers=buyer)).status_code == 409
    assert (await client.post(f"{API}/orders/{order['id']}/mock-payment", headers=buyer)).status_code == 409


async def test_orders_are_private(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    stranger = await user_headers(client, "stranger@kairos.dev")
    pid = (await create_product(client, seller))["id"]
    order = (await checkout(client, buyer, pid, 1))["order"]

    assert (await client.get(f"{API}/orders/{order['id']}", headers=stranger)).status_code == 404
    assert (await client.post(f"{API}/orders/{order['id']}/cancel", headers=stranger)).status_code == 404


async def test_failed_payment_webhook_is_idempotent(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    pid = (await create_product(client, seller, stock_quantity=10))["id"]
    result = await checkout(client, buyer, pid, 2)
    assert await product_stock(client, pid) == 8

    event = {
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": result["payment_intent_id"], "last_payment_error": None}},
    }
    for _ in range(2):   # Stripe delivers at-least-once
        r = await client.post(f"{API}/webhooks/stripe", json=event)
        assert r.status_code == 200, r.text

    assert await product_stock(client, pid) == 10   # restored exactly once
    order = (await client.get(f"{API}/orders/{result['order']['id']}", headers=buyer)).json()
    assert order["status"] == "payment_failed"


async def test_payment_succeeded_webhook(client):
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    pid = (await create_product(client, seller))["id"]
    result = await checkout(client, buyer, pid, 1)

    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": result["payment_intent_id"], "amount": 11800, "currency": "inr"}},
    }
    for _ in range(2):
        assert (await client.post(f"{API}/webhooks/stripe", json=event)).status_code == 200

    order = (await client.get(f"{API}/orders/{result['order']['id']}", headers=buyer)).json()
    assert order["status"] == "paid"


async def test_admin_fulfilment_flow(client):
    admin = await admin_headers(client)
    seller = await user_headers(client, "seller@kairos.dev", "seller")
    buyer = await user_headers(client, "buyer@kairos.dev")
    pid = (await create_product(client, seller))["id"]
    order_id = (await checkout(client, buyer, pid, 1))["order"]["id"]
    await client.post(f"{API}/orders/{order_id}/mock-payment", headers=buyer)

    assert (await client.patch(f"{API}/orders/{order_id}/status", json={"status": "processing"}, headers=buyer)).status_code == 403

    for next_status in ("processing", "shipped", "delivered"):
        r = await client.patch(f"{API}/orders/{order_id}/status", json={"status": next_status}, headers=admin)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == next_status

    backwards = await client.patch(f"{API}/orders/{order_id}/status", json={"status": "processing"}, headers=admin)
    assert backwards.status_code == 409

    everything = (await client.get(f"{API}/orders/all", headers=admin)).json()
    assert everything["total"] == 1
