from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.cart import CartAddRequest, CartResponse, CartUpdateRequest
from app.services.auth_service import get_current_user
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CartResponse, summary="View your cart")
async def get_cart(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Fetch all items currently in the authenticated user's cart."""
    service = CartService(db, redis)
    return await service.get_cart(str(current_user.id))


@router.post("", response_model=CartResponse, summary="Add item to cart")
async def add_to_cart(
    payload: CartAddRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """
    Add a product to the cart.
    If the product is already in the cart, the quantity is increased.
    The **current Kairos dynamic price** is stored at time of adding.
    """
    service = CartService(db, redis)
    return await service.add_item(str(current_user.id), payload)


@router.patch("", response_model=CartResponse, summary="Update item quantity")
async def update_cart_item(
    payload: CartUpdateRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """
    Update the quantity of an item in the cart.
    Set `quantity` to **0** to remove the item entirely.
    """
    service = CartService(db, redis)
    return await service.update_item(str(current_user.id), payload)


@router.delete("", summary="Clear entire cart")
async def clear_cart(
    redis: aioredis.Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove all items from the cart."""
    service = CartService(db, redis)
    await service.clear_cart(str(current_user.id))
    return {"message": "Cart cleared"}
