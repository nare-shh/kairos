import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.category import CategoryCreateRequest, CategoryResponse
from app.services.auth_service import require_role
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category (admin only)",
)
async def create_category(
    payload: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Create a new product category.
    Set `parent_id` to create a sub-category.

    **Authorization:** Admin only
    """
    return await CategoryService(db).create(payload)


@router.get("", response_model=list[CategoryResponse], summary="List all categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """
    Returns all categories. Public endpoint.
    Each category includes its `parent_id` — build the tree on the frontend.
    """
    return await CategoryService(db).list_all()


@router.get("/{category_id}", response_model=CategoryResponse, summary="Get a category")
async def get_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await CategoryService(db).get(category_id)


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update a category (admin only)",
)
async def update_category(
    category_id: uuid.UUID,
    payload: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    return await CategoryService(db).update(category_id, payload)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (admin only)",
)
async def delete_category(
    category_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Delete a category. Fails if any products are assigned to it.
    Reassign or delete those products first.
    """
    await CategoryService(db).delete(category_id)
