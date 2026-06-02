from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    AccessTokenResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import AuthService, get_current_user

# APIRouter is like a mini-app — groups related endpoints together
# prefix="/auth" means all routes here start with /auth
# tags=["Auth"] groups them under one section in Swagger UI
router = APIRouter(prefix="/auth", tags=["Auth"])


# ─── POST /auth/register ──────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,   # 201 = new resource created (not 200)
    summary="Register a new user account",
)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user account.

    - **email**: Must be valid and unique
    - **password**: Min 8 chars, must include uppercase + digit
    - **role**: `customer` (default) or `seller`
    """
    service = AuthService(db)
    return await service.register(payload)


# ─── POST /auth/login ─────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive JWT tokens",
)
async def login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email + password.

    Returns:
    - **access_token** → use in `Authorization: Bearer <token>` header, expires in 30 min
    - **refresh_token** → use to get a new access token, expires in 7 days
    """
    service = AuthService(db)
    return await service.login(payload.email, payload.password)


# ─── POST /auth/refresh ───────────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Get a new access token using refresh token",
)
async def refresh_token(
    payload: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    When your access token expires (you get a 401), call this with your
    refresh token to get a brand-new access token without logging in again.
    """
    service = AuthService(db)
    return await service.refresh_access_token(payload.refresh_token)


# ─── GET /auth/me ─────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user's profile",
)
async def get_me(
    # Depends(get_current_user) = protected route
    # FastAPI reads the JWT from "Authorization: Bearer <token>",
    # validates it, fetches the user from DB, and passes it here
    current_user: User = Depends(get_current_user),
):
    """
    Returns the profile of whoever is currently logged in.
    **Requires Authorization: Bearer token.**
    """
    return current_user
