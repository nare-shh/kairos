import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class CartAddRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=100, description="Must be between 1 and 100")


class CartUpdateRequest(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(..., ge=0, description="Set to 0 to remove item from cart")


class CartItemResponse(BaseModel):
    product_id: str
    product_name: str
    sku: str
    quantity: int
    unit_price: Decimal       # current_price when item was added (may have changed since!)
    total_price: Decimal
    stock_available: int
    is_in_stock: bool


class CartResponse(BaseModel):
    user_id: str
    items: list[CartItemResponse]
    item_count: int
    subtotal: Decimal
    is_empty: bool
