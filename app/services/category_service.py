import uuid
from re import sub

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.schemas.category import CategoryCreateRequest, CategoryResponse


def slugify(text: str) -> str:
    text = text.lower()
    text = sub(r"[^\w\s-]", "", text)
    text = sub(r"[\s_-]+", "-", text)
    text = sub(r"^-+|-+$", "", text)
    return text


class CategoryService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── CREATE ─────────────────────────────────────────────────────────────────
    async def create(self, data: CategoryCreateRequest) -> CategoryResponse:
        # Check name uniqueness
        existing = await self.db.execute(
            select(Category).where(Category.name == data.name)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{data.name}' already exists",
            )

        # Validate parent exists
        if data.parent_id:
            parent = await self.db.execute(
                select(Category).where(Category.id == data.parent_id)
            )
            if not parent.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent category {data.parent_id} not found",
                )

        # Build unique slug
        base_slug = slugify(data.name)
        slug = base_slug
        slug_check = await self.db.execute(
            select(Category).where(Category.slug == slug)
        )
        if slug_check.scalar_one_or_none():
            slug = f"{base_slug}-{str(uuid.uuid4())[:6]}"

        category = Category(
            name=data.name,
            slug=slug,
            description=data.description,
            parent_id=data.parent_id,
        )
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return CategoryResponse.model_validate(category)

    # ── LIST (tree-aware) ──────────────────────────────────────────────────────
    async def list_all(self) -> list[CategoryResponse]:
        """
        Returns all categories.
        Tree structure is resolved client-side using parent_id.
        This is simpler and more flexible than returning a nested tree from the API.
        """
        result = await self.db.execute(
            select(Category).order_by(Category.name)
        )
        categories = result.scalars().all()
        return [CategoryResponse.model_validate(c) for c in categories]

    # ── GET SINGLE ─────────────────────────────────────────────────────────────
    async def get(self, category_id: uuid.UUID) -> CategoryResponse:
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return CategoryResponse.model_validate(category)

    # ── UPDATE ─────────────────────────────────────────────────────────────────
    async def update(self, category_id: uuid.UUID, data: CategoryCreateRequest) -> CategoryResponse:
        result = await self.db.execute(
            select(Category).where(Category.id == category_id)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        # Check name conflict (exclude self)
        if data.name != category.name:
            name_check = await self.db.execute(
                select(Category).where(
                    Category.name == data.name,
                    Category.id != category_id,
                )
            )
            if name_check.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Category '{data.name}' already exists",
                )
            category.name = data.name
            category.slug = slugify(data.name)

        if data.description is not None:
            category.description = data.description
        if data.parent_id is not None:
            category.parent_id = data.parent_id

        await self.db.flush()
        await self.db.refresh(category)
        return CategoryResponse.model_validate(category)

    # ── DELETE ─────────────────────────────────────────────────────────────────
    async def delete(self, category_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(Category)
            .where(Category.id == category_id)
            .options(selectinload(Category.products))
        )
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        if category.products:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete: {len(category.products)} products are using this category. "
                       "Reassign or delete the products first.",
            )

        await self.db.delete(category)
        await self.db.flush()
