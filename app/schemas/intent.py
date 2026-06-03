import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.events.types import IntentEvent


class IntentTrackRequest(BaseModel):
    """
    Sent by the frontend every time a user interacts with a product.

    Examples:
    - User opens product page       → event_type = "ProductViewed"
    - User clicks "Add to Cart"     → event_type = "CartAdded"
    - User starts checkout          → event_type = "CheckoutStarted"
    - User closes checkout midway   → event_type = "CheckoutAbandoned"

    This stream of events is what feeds the pricing engine.
    The more intent signals we collect, the better the pricing decisions.
    """

    product_id: uuid.UUID = Field(..., description="The product being interacted with")

    event_type: IntentEvent = Field(
        ...,
        description="Type of user interaction",
        examples=[IntentEvent.PRODUCT_VIEWED, IntentEvent.CART_ADDED],
    )

    # Optional context — enriches the signal
    session_id: str | None = Field(
        None,
        description="Browser session ID — links events from the same browsing session",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Extra context: page_source, device_type, time_on_page, etc.",
    )


class IntentScoreResponse(BaseModel):
    """
    The current demand state for a product — returned by the scoring API.
    Shows what the pricing engine sees right now.
    """

    product_id: uuid.UUID
    demand_score: float = Field(..., description="Aggregated weighted score (last 1 hour)")
    demand_level: str = Field(
        ..., description="Human label: low | medium | high | surge"
    )
    active_viewers: int = Field(..., description="Unique sessions viewing in last 15 min")
    cart_adds_1h: int = Field(..., description="Cart additions in last 1 hour")
    price_multiplier: float = Field(..., description="Current multiplier applied to base price")
    current_price: float
    base_price: float
    calculated_at: datetime
