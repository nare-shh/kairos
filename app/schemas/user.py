import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Base ─────────────────────────────────────────────────────────────────────
# UserBase holds fields shared across multiple schemas
# We inherit from this to avoid repeating ourselves (DRY principle)
class UserBase(BaseModel):
    email: EmailStr                          # EmailStr validates email format automatically
    full_name: str | None = Field(None, max_length=255)


# ─── Request Schemas (what the client SENDS) ──────────────────────────────────

class UserRegisterRequest(UserBase):
    # Password rules enforced here — before hitting the database
    password: str = Field(
        ...,              # "..." means this field is required (no default)
        min_length=8,
        max_length=100,
        description="Must be at least 8 characters",
    )
    role: str = Field(default="customer", pattern="^(customer|seller)$")
    # Regex pattern: only "customer" or "seller" allowed on registration
    # "admin" cannot self-register — must be assigned manually

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        field_validator runs AFTER pydantic's type checks.
        We add custom business rules here.
        """
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


# ─── Response Schemas (what we SEND BACK to the client) ───────────────────────

class UserResponse(UserBase):
    # We return these fields — but NEVER the hashed_password
    id: uuid.UUID
    role: str
    is_active: bool
    created_at: datetime

    # model_config tells Pydantic this schema is backed by a SQLAlchemy model
    # Without this, Pydantic can't read SQLAlchemy ORM objects
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"     # OAuth2 standard: always "bearer"
    expires_in: int                # seconds until access token expires


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ─── Internal schema (used inside the app, not exposed to clients) ─────────────
class TokenPayload(BaseModel):
    # This is what we encode INSIDE the JWT token
    sub: str           # "subject" — standard JWT claim, we store user ID here
    role: str
    exp: int           # expiry timestamp — standard JWT claim
    type: str          # "access" or "refresh" — prevents using refresh as access
