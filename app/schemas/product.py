import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


# ─── Request Schemas ──────────────────────────────────────────────────────────

class ProductCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None
    sku: str = Field(..., min_length=2, max_length=100)

    # Price fields — all required on creation
    base_price: Decimal = Field(..., gt=0, description="Must be greater than 0")
    min_price: Decimal = Field(..., gt=0, description="Floor: Kairos won't price below this")
    max_price: Decimal = Field(..., gt=0, description="Ceiling: Kairos won't price above this")

    stock_quantity: int = Field(default=0, ge=0)   # ge=0 means >= 0 (can't be negative)
    low_stock_threshold: int = Field(default=10, ge=1)
    category_id: uuid.UUID | None = None
    attributes: dict = Field(default_factory=dict)

    @field_validator("sku")
    @classmethod
    def sku_format(cls, v: str) -> str:
        """SKU must be uppercase alphanumeric with hyphens only."""
        cleaned = v.upper().replace(" ", "-")
        return cleaned

    @model_validator(mode="after")
    def validate_price_range(self) -> "ProductCreateRequest":
        """
        model_validator runs AFTER all individual field validators.
        We use it to validate rules that involve MULTIPLE fields together.
        min_price must be <= base_price <= max_price
        """
        if self.min_price > self.base_price:
            raise ValueError("min_price cannot be greater than base_price")
        if self.base_price > self.max_price:
            raise ValueError("base_price cannot be greater than max_price")
        return self


class ProductUpdateRequest(BaseModel):
    """
    All fields are optional — clients only send what they want to change.
    This is called a PATCH-style update (vs PUT which requires all fields).
    """
    name: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = None
    stock_quantity: int | None = Field(None, ge=0)
    low_stock_threshold: int | None = Field(None, ge=1)
    category_id: uuid.UUID | None = None
    attributes: dict | None = None

    # Price updates are separate (they generate a specific event type)
    min_price: Decimal | None = Field(None, gt=0)
    max_price: Decimal | None = Field(None, gt=0)


class ProductPriceUpdateRequest(BaseModel):
    """
    Explicit price change endpoint — generates a ProductPriceChanged event.
    Separate from general update so the intent is clear and auditable.
    """
    new_base_price: Decimal = Field(..., gt=0)
    reason: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Required: explain WHY the price changed (stored in event log)",
        # This reason is stored in the event payload — full audit trail
    )


class StockUpdateRequest(BaseModel):
    quantity_delta: int = Field(
        ...,
        description="Positive = add stock, Negative = remove stock"
    )
    reason: str = Field(..., min_length=3)


# ─── Response Schemas ─────────────────────────────────────────────────────────

class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    sku: str
    base_price: Decimal
    current_price: Decimal
    min_price: Decimal
    max_price: Decimal
    stock_quantity: int
    status: str
    is_active: bool
    images: list
    attributes: dict
    category_id: uuid.UUID | None
    seller_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """Paginated list wrapper — every list endpoint should return this."""
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    pages: int                          # total number of pages


class EventStoreResponse(BaseModel):
    """Response shape for reading events from the store."""
    id: int
    event_id: uuid.UUID
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict
    version: int
    occurred_at: datetime
    caused_by: str | None

    model_config = {"from_attributes": True}
