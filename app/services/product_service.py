import uuid
from math import ceil
from decimal import Decimal
from re import sub

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events.publisher import KafkaTopic, publish_event
from app.events.types import ProductEvent
from app.models.category import Category
from app.models.event_store import EventStore
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    ProductCreateRequest,
    ProductListResponse,
    ProductPriceUpdateRequest,
    ProductResponse,
    ProductUpdateRequest,
    StockUpdateRequest,
)


def slugify(text: str) -> str:
    """
    Convert any string into a URL-safe slug.
    "Men's Running Shoes" → "mens-running-shoes"

    Steps:
    1. Lowercase everything
    2. Replace non-alphanumeric characters with hyphens
    3. Collapse multiple hyphens into one
    4. Strip leading/trailing hyphens
    """
    text = text.lower()
    text = sub(r"[^\w\s-]", "", text)     # remove special chars except hyphens
    text = sub(r"[\s_-]+", "-", text)     # spaces/underscores → hyphens
    text = sub(r"^-+|-+$", "", text)      # strip leading/trailing hyphens
    return text


class ProductService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Private: Save Event ────────────────────────────────────────────────────
    async def _save_event(
        self,
        aggregate_id: str,
        event_type: str,
        payload: dict,
        version: int,
        caused_by: str | None = None,
    ) -> EventStore:
        """
        Core event sourcing method — called by EVERY write operation.

        This is a private helper (_name convention = internal use only).
        Every service method that changes state calls this FIRST.
        The event is the source of truth — the product table update comes after.

        Returns the saved EventStore record.
        """
        event = EventStore(
            event_id=uuid.uuid4(),
            aggregate_type="product",
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            version=version,
            caused_by=caused_by,
            metadata_={
                "service": "product_service",
                "version": "1.0",
            },
        )
        self.db.add(event)
        await self.db.flush()   # write to DB within the transaction (not committed yet)
        return event

    # ── CREATE ─────────────────────────────────────────────────────────────────
    async def create_product(
        self, data: ProductCreateRequest, seller: User
    ) -> ProductResponse:
        """
        Create a product.

        Event sourcing flow:
        1. Validate inputs (check SKU uniqueness, category exists)
        2. Save "ProductCreated" event to event_store
        3. Create the product row (the read model projection)
        4. Publish event to Kafka (for streaming consumers)
        5. Return the product
        """

        # 1a. Check SKU uniqueness
        existing = await self.db.execute(
            select(Product).where(Product.sku == data.sku)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A product with SKU '{data.sku}' already exists",
            )

        # 1b. Validate category if provided
        if data.category_id:
            cat_result = await self.db.execute(
                select(Category).where(Category.id == data.category_id)
            )
            if not cat_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Category {data.category_id} not found",
                )

        # 1c. Build a unique slug (append short UUID if name-based slug conflicts)
        base_slug = slugify(data.name)
        slug = base_slug
        slug_check = await self.db.execute(
            select(Product).where(Product.slug == slug)
        )
        if slug_check.scalar_one_or_none():
            slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

        product_id = str(uuid.uuid4())

        # 2. Save event FIRST — this is the golden rule of event sourcing
        #    If we saved the product first and the event save failed,
        #    we'd have a product with no history. Bad.
        #    If we save the event first and product save fails, we roll back both.
        await self._save_event(
            aggregate_id=product_id,
            event_type=ProductEvent.CREATED,
            payload={
                "name": data.name,
                "sku": data.sku,
                "base_price": str(data.base_price),
                "min_price": str(data.min_price),
                "max_price": str(data.max_price),
                "stock_quantity": data.stock_quantity,
                "category_id": str(data.category_id) if data.category_id else None,
                "seller_id": str(seller.id),
                "attributes": data.attributes,
            },
            version=1,
            caused_by=str(seller.id),
        )

        # 3. Create the product row (projection / read model)
        product = Product(
            id=uuid.UUID(product_id),
            name=data.name,
            slug=slug,
            description=data.description,
            sku=data.sku,
            base_price=data.base_price,
            current_price=data.base_price,    # current = base on creation
            min_price=data.min_price,
            max_price=data.max_price,
            stock_quantity=data.stock_quantity,
            low_stock_threshold=data.low_stock_threshold,
            category_id=data.category_id,
            seller_id=seller.id,
            attributes=data.attributes,
            status="active",
            is_active=True,
        )
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)

        # 4. Publish to Kafka — async, non-blocking, failure-safe
        await publish_event(
            topic=KafkaTopic.PRODUCT_EVENTS,
            event_type=ProductEvent.CREATED,
            aggregate_id=product_id,
            payload={"product_id": product_id, "name": data.name, "price": str(data.base_price)},
            caused_by=str(seller.id),
        )

        return ProductResponse.model_validate(product)

    # ── READ: Get Single Product ───────────────────────────────────────────────
    async def get_product(self, product_id: uuid.UUID) -> ProductResponse:
        result = await self.db.execute(
            select(Product)
            .where(Product.id == product_id, Product.is_active == True)  # noqa: E712
            .options(selectinload(Product.category))
            # selectinload = load the category in a separate query (not a JOIN)
            # More efficient for one-to-many when you need the related object
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found",
            )
        return ProductResponse.model_validate(product)

    # ── READ: List Products (with pagination) ──────────────────────────────────
    async def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        category_id: uuid.UUID | None = None,
        seller_id: uuid.UUID | None = None,
        search: str | None = None,
    ) -> ProductListResponse:
        """
        Pagination explained:
        - page=1, page_size=20 → rows 1-20
        - page=2, page_size=20 → rows 21-40
        - offset = (page - 1) * page_size
        """
        # Build the base query with filters
        query = select(Product).where(Product.is_active == True)  # noqa: E712
        count_query = select(func.count(Product.id)).where(Product.is_active == True)  # noqa: E712

        if category_id:
            query = query.where(Product.category_id == category_id)
            count_query = count_query.where(Product.category_id == category_id)

        if seller_id:
            query = query.where(Product.seller_id == seller_id)
            count_query = count_query.where(Product.seller_id == seller_id)

        if search:
            # ilike = case-insensitive LIKE search
            # % = wildcard, so %shoes% matches "Running Shoes", "Shoes Store" etc.
            query = query.where(Product.name.ilike(f"%{search}%"))
            count_query = count_query.where(Product.name.ilike(f"%{search}%"))

        # Get total count (for pagination metadata)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(Product.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        products = result.scalars().all()

        return ProductListResponse(
            items=[ProductResponse.model_validate(p) for p in products],
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total > 0 else 0,
        )

    # ── UPDATE ─────────────────────────────────────────────────────────────────
    async def update_product(
        self, product_id: uuid.UUID, data: ProductUpdateRequest, seller: User
    ) -> ProductResponse:
        product = await self._get_owned_product(product_id, seller)

        # Track what changed (for the event payload)
        changes = {}
        if data.name is not None and data.name != product.name:
            changes["name"] = {"old": product.name, "new": data.name}
            product.name = data.name
            product.slug = slugify(data.name)

        if data.description is not None:
            changes["description"] = {"old": product.description, "new": data.description}
            product.description = data.description

        if data.stock_quantity is not None and data.stock_quantity != product.stock_quantity:
            changes["stock_quantity"] = {"old": product.stock_quantity, "new": data.stock_quantity}
            product.stock_quantity = data.stock_quantity

        if data.low_stock_threshold is not None:
            changes["low_stock_threshold"] = {
                "old": product.low_stock_threshold,
                "new": data.low_stock_threshold,
            }
            product.low_stock_threshold = data.low_stock_threshold

        if data.category_id is not None:
            changes["category_id"] = {
                "old": str(product.category_id),
                "new": str(data.category_id),
            }
            product.category_id = data.category_id

        if data.attributes is not None:
            changes["attributes"] = {"old": product.attributes, "new": data.attributes}
            product.attributes = data.attributes

        if not changes:
            # Nothing actually changed — no point creating an event
            return ProductResponse.model_validate(product)

        # Get current event version for this product
        version = await self._get_next_version(str(product_id))

        await self._save_event(
            aggregate_id=str(product_id),
            event_type=ProductEvent.UPDATED,
            payload={"changes": changes},
            version=version,
            caused_by=str(seller.id),
        )

        await self.db.flush()
        await self.db.refresh(product)
        return ProductResponse.model_validate(product)

    # ── PRICE CHANGE (The Kairos novelty!) ────────────────────────────────────
    async def change_price(
        self, product_id: uuid.UUID, data: ProductPriceUpdateRequest, seller: User
    ) -> ProductResponse:
        """
        Price change is its own endpoint + its own event type.
        This is intentional: price changes are high-value audit events.
        "Why was this product $99 last Tuesday?" → query event_store for ProductPriceChanged

        The event payload stores:
        - old price (what it was before)
        - new price (what it changed to)
        - the REASON (required — improves audit quality enormously)
        """
        product = await self._get_owned_product(product_id, seller)
        old_price = product.base_price

        if data.new_base_price < product.min_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New price {data.new_base_price} is below minimum allowed price {product.min_price}",
            )
        if data.new_base_price > product.max_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New price {data.new_base_price} exceeds maximum allowed price {product.max_price}",
            )

        version = await self._get_next_version(str(product_id))

        # Save event with rich payload — this IS the audit trail
        await self._save_event(
            aggregate_id=str(product_id),
            event_type=ProductEvent.PRICE_CHANGED,
            payload={
                "old_base_price": str(old_price),
                "new_base_price": str(data.new_base_price),
                "reason": data.reason,
                # current_price is separate — controlled by Kairos pricing engine
                "current_price_unchanged": True,
            },
            version=version,
            caused_by=str(seller.id),
        )

        # Update the read model
        product.base_price = data.new_base_price

        await publish_event(
            topic=KafkaTopic.PRODUCT_EVENTS,
            event_type=ProductEvent.PRICE_CHANGED,
            aggregate_id=str(product_id),
            payload={
                "product_id": str(product_id),
                "old_price": str(old_price),
                "new_price": str(data.new_base_price),
                "reason": data.reason,
            },
            caused_by=str(seller.id),
        )

        await self.db.flush()
        await self.db.refresh(product)
        return ProductResponse.model_validate(product)

    # ── STOCK UPDATE ───────────────────────────────────────────────────────────
    async def update_stock(
        self, product_id: uuid.UUID, data: StockUpdateRequest, seller: User
    ) -> ProductResponse:
        product = await self._get_owned_product(product_id, seller)

        new_qty = product.stock_quantity + data.quantity_delta

        if new_qty < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reduce stock below 0. Current: {product.stock_quantity}, Delta: {data.quantity_delta}",
            )

        version = await self._get_next_version(str(product_id))

        await self._save_event(
            aggregate_id=str(product_id),
            event_type=ProductEvent.STOCK_UPDATED,
            payload={
                "old_quantity": product.stock_quantity,
                "new_quantity": new_qty,
                "delta": data.quantity_delta,
                "reason": data.reason,
                "is_low_stock": new_qty <= product.low_stock_threshold,
            },
            version=version,
            caused_by=str(seller.id),
        )

        product.stock_quantity = new_qty
        await self.db.flush()
        await self.db.refresh(product)
        return ProductResponse.model_validate(product)

    # ── GET EVENT HISTORY ─────────────────────────────────────────────────────
    async def get_product_events(self, product_id: uuid.UUID) -> list[EventStore]:
        """
        Return the complete event history for a product.
        This is event sourcing's superpower — the full audit trail on demand.
        """
        result = await self.db.execute(
            select(EventStore)
            .where(
                EventStore.aggregate_type == "product",
                EventStore.aggregate_id == str(product_id),
            )
            .order_by(EventStore.id.asc())   # always return in chronological order
        )
        return result.scalars().all()

    # ── Private Helpers ───────────────────────────────────────────────────────
    async def _get_owned_product(self, product_id: uuid.UUID, seller: User) -> Product:
        """
        Fetch a product AND verify the requesting user owns it.
        Admins can access any product; sellers only their own.
        """
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Authorization check: seller can only modify their own products
        if seller.role != "admin" and product.seller_id != seller.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to modify this product",
            )
        return product

    async def _get_next_version(self, aggregate_id: str) -> int:
        """Get the next version number for an aggregate's events."""
        result = await self.db.execute(
            select(func.max(EventStore.version))
            .where(
                EventStore.aggregate_type == "product",
                EventStore.aggregate_id == aggregate_id,
            )
        )
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1
