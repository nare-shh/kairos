import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class CartAddRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=100, description="Must be between 1 and 100")


class CartUpdateRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=0, le=100, description="Set to 0 to remove item from cart")


class CartItemResponse(BaseModel):
    product_id: str
    product_name: str
    sku: str
    quantity: int
    unit_price: Decimal        # LIVE Kairos price — what checkout will charge
    added_unit_price: Decimal  # price when the item was put in the cart
    price_changed: bool        # unit_price != added_unit_price
    total_price: Decimal
    stock_available: int
    is_in_stock: bool          # False if sold out, deactivated or deleted


class CartResponse(BaseModel):
    user_id: str
    items: list[CartItemResponse]
    item_count: int
    subtotal: Decimal
    is_empty: bool
