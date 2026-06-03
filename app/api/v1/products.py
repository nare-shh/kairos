import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.product import (
    EventStoreResponse,
    ProductCreateRequest,
    ProductListResponse,
    ProductPriceUpdateRequest,
    ProductResponse,
    ProductUpdateRequest,
    StockUpdateRequest,
)
from app.services.auth_service import get_current_user, require_role
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


# ─── POST /products — Create a product ───────────────────────────────────────
@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
)
async def create_product(
    payload: ProductCreateRequest,
    db: AsyncSession = Depends(get_db),
    # require_role("seller", "admin") = only sellers and admins can create products
    current_user: User = Depends(require_role("seller", "admin")),
):
    """
    Create a new product listing.

    **Authorization:** Seller or Admin only

    The `base_price` becomes the starting `current_price`.
    Kairos will dynamically adjust `current_price` based on demand signals.
    The `min_price` and `max_price` define the safe range Kairos operates within.
    """
    service = ProductService(db)
    return await service.create_product(payload, current_user)


# ─── GET /products — List products (public) ──────────────────────────────────
@router.get(
    "",
    response_model=ProductListResponse,
    summary="List all active products",
)
async def list_products(
    # Query() = parameters from the URL query string: /products?page=2&search=shoes
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100),
    category_id: uuid.UUID | None = Query(default=None),
    seller_id: uuid.UUID | None = Query(default=None),
    search: str | None = Query(default=None, min_length=2, description="Search by name"),
    db: AsyncSession = Depends(get_db),
    # No auth required — browsing is public
):
    """
    List all active products with pagination and optional filters.
    This is a public endpoint — no authentication required.
    """
    service = ProductService(db)
    return await service.list_products(page, page_size, category_id, seller_id, search)


# ─── GET /products/{id} — Get single product ─────────────────────────────────
@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get a single product by ID",
)
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single product by its UUID. Public endpoint."""
    service = ProductService(db)
    return await service.get_product(product_id)


# ─── PATCH /products/{id} — Update product ───────────────────────────────────
@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update product details",
)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("seller", "admin")),
):
    """
    Update product name, description, stock threshold, or category.

    **Authorization:** Only the product's seller or an admin.
    All changes are recorded as a `ProductUpdated` event in the audit log.
    """
    service = ProductService(db)
    return await service.update_product(product_id, payload, current_user)


# ─── PUT /products/{id}/price — Change price ─────────────────────────────────
@router.put(
    "/{product_id}/price",
    response_model=ProductResponse,
    summary="Change a product's base price",
)
async def change_price(
    product_id: uuid.UUID,
    payload: ProductPriceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("seller", "admin")),
):
    """
    Explicitly change a product's base price.

    This endpoint is separate from general update because price changes
    are high-value audit events. A `reason` is required and stored in
    the event log permanently.

    Kairos will use `base_price` as the anchor for dynamic pricing.
    The actual `current_price` shown to buyers may differ based on demand.
    """
    service = ProductService(db)
    return await service.change_price(product_id, payload, current_user)


# ─── PATCH /products/{id}/stock — Update stock ───────────────────────────────
@router.patch(
    "/{product_id}/stock",
    response_model=ProductResponse,
    summary="Adjust stock quantity",
)
async def update_stock(
    product_id: uuid.UUID,
    payload: StockUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("seller", "admin")),
):
    """
    Adjust stock. Use positive delta to add, negative to remove.

    Example: `{"quantity_delta": -5, "reason": "damaged goods"}` removes 5 units.

    Each adjustment is recorded as a `ProductStockUpdated` event.
    Low stock events trigger Kairos pricing adjustments.
    """
    service = ProductService(db)
    return await service.update_stock(product_id, payload, current_user)


# ─── GET /products/{id}/events — Full event history ──────────────────────────
@router.get(
    "/{product_id}/events",
    response_model=list[EventStoreResponse],
    summary="Get full event history for a product",
)
async def get_product_events(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    # Only sellers/admins can see raw event history
    current_user: User = Depends(require_role("seller", "admin")),
):
    """
    **The Kairos superpower: full audit trail.**

    Returns every event that ever happened to this product — in order.
    You can see every price change, stock update, and who made each change.

    This is the event sourcing read endpoint — the immutable history.
    """
    service = ProductService(db)
    events = await service.get_product_events(product_id)
    return [EventStoreResponse.model_validate(e) for e in events]
