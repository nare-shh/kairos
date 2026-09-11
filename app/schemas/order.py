import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ShippingAddress(BaseModel):
    full_name: str = Field(..., min_length=2)
    line1: str = Field(..., min_length=5, description="Street address")
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str = Field(default="IN", min_length=2, max_length=2)
    phone: str | None = None


class CheckoutRequest(BaseModel):
    shipping_address: ShippingAddress
    notes: str | None = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_sku: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str
    user_id: uuid.UUID
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    shipping_amount: Decimal
    total_amount: Decimal
    shipping_address: dict
    notes: str | None
    items: list[OrderItemResponse]
    created_at: datetime
    paid_at: datetime | None
    # Note: stripe_client_secret intentionally excluded from list response
    # Only returned on creation (single use) and via GET /orders/{id}/payment

    model_config = {"from_attributes": True}


class CheckoutResponse(BaseModel):
    """Returned immediately after checkout — contains the Stripe client secret."""
    order: OrderResponse
    # client_secret is what the frontend passes to Stripe.js to complete payment
    # Format: pi_3ABC123_secret_XYZ
    # NEVER log this value — it's a single-use payment credential
    client_secret: str
    payment_intent_id: str
    amount_to_pay: Decimal
    currency: str = "inr"
    # True when Stripe isn't configured: pay via POST /orders/{id}/mock-payment
    mock_payment: bool = False


class OrderPaymentResponse(BaseModel):
    """Lets the customer resume payment for an unpaid order."""
    order_id: uuid.UUID
    client_secret: str
    payment_intent_id: str
    amount_to_pay: Decimal
    currency: str = "inr"
    mock_payment: bool


class OrderStatusUpdateRequest(BaseModel):
    """Admin fulfilment: paid → processing → shipped → delivered."""
    status: Literal["processing", "shipped", "delivered"]


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
