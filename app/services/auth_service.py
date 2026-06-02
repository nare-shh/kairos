import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    AccessTokenResponse,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)

# HTTPBearer extracts the token from the "Authorization: Bearer <token>" header
# auto_error=True means FastAPI returns 403 automatically if header is missing
bearer_scheme = HTTPBearer(auto_error=True)


class AuthService:
    """
    Service layer = business logic lives here, NOT in the route handlers.
    Routes should be thin: receive request → call service → return response.
    This separation makes code testable and reusable.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserRegisterRequest) -> UserResponse:
        """Create a new user account."""

        # Step 1: Check if email is already taken
        result = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        existing = result.scalar_one_or_none()
        # scalar_one_or_none() returns the user object if found, None if not
        # scalar_one() would raise an exception if not found — we don't want that here

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
                # 409 Conflict — semantically correct: the resource already exists
            )

        # Step 2: Hash the password — NEVER store the plain text
        hashed = hash_password(data.password)

        # Step 3: Create the user object (not saved to DB yet)
        user = User(
            id=uuid.uuid4(),
            email=data.email,
            full_name=data.full_name,
            hashed_password=hashed,
            role=data.role,
        )

        # Step 4: Add to session and flush
        # add() stages the object — like git add
        # flush() sends the SQL INSERT to the DB but doesn't commit yet
        # The session.commit() in get_db() will commit when the request ends
        self.db.add(user)
        await self.db.flush()
        # flush() is needed here so we get the user.id back from the DB
        await self.db.refresh(user)
        # refresh() re-reads the row from DB so all fields (like created_at) are populated

        # Step 5: Return using Pydantic schema — strips hashed_password from response
        return UserResponse.model_validate(user)

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate user and return JWT tokens."""

        # Step 1: Find user by email
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        # Step 2: Verify credentials
        # IMPORTANT: We use the same error message whether the email OR password is wrong.
        # This prevents "user enumeration" attacks (attacker can't tell if email exists).
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
                # WWW-Authenticate header is required by HTTP spec for 401 responses
            )

        # Step 3: Check if account is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Contact support.",
            )

        # Step 4: Create both tokens
        user_id = str(user.id)
        access_token = create_access_token(user_id, user.role)
        refresh_token = create_refresh_token(user_id, user.role)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=60 * 30,    # 30 minutes in seconds
        )

    async def refresh_access_token(self, refresh_token: str) -> AccessTokenResponse:
        """Exchange a valid refresh token for a new access token."""

        # Step 1: Decode and validate the refresh token
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        # Step 2: Make sure this is actually a refresh token (not an access token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        # Step 3: Verify the user still exists and is active
        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated",
            )

        # Step 4: Issue a fresh access token
        new_access_token = create_access_token(str(user.id), user.role)
        return AccessTokenResponse(
            access_token=new_access_token,
            expires_in=60 * 30,
        )


# ─── Dependency: get current user from JWT ────────────────────────────────────
# This function is injected into any route that requires authentication.
# FastAPI calls it automatically and passes the result as a parameter.

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extracts + validates the JWT from the Authorization header.
    Returns the User object if valid.
    Raises 401 if token is missing, expired, or tampered with.

    Usage in a route:
        @router.get("/me")
        async def me(user: User = Depends(get_current_user)):
            return user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Fetch user from DB to ensure they still exist and are active
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*roles: str):
    """
    Role-based access control (RBAC) dependency factory.
    Creates a dependency that allows only specific roles.

    Usage:
        @router.delete("/products/{id}")
        async def delete(user = Depends(require_role("admin", "seller"))):
            ...
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(roles)}",
            )
        return current_user
    return role_checker
