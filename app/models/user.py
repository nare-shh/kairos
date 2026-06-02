import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    # __tablename__ tells SQLAlchemy which table this maps to in PostgreSQL
    __tablename__ = "users"

    # UUID primary key — better than integer IDs in production because:
    # 1. Can be generated on the client without hitting the DB
    # 2. Not guessable (security — users can't enumerate IDs)
    # 3. Safe to expose in URLs
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,   # auto-generate a new UUID for each row
    )

    # Email — must be unique across all users (acts as login identifier)
    # index=True adds a DB index → fast lookups by email
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # Full name — optional (nullable=True means it can be NULL in the DB)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # hashed_password — NEVER store plain-text passwords
    # We store the bcrypt hash, not the original password
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)

    # Role — controls what the user can do
    # "customer" → can browse + buy
    # "seller"   → can list products
    # "admin"    → full access
    role: Mapped[str] = mapped_column(
        Enum("customer", "seller", "admin", name="user_role_enum"),
        default="customer",
        nullable=False,
    )

    # is_active — soft delete / account suspension flag
    # False = banned or unverified, True = normal access
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps — created_at and updated_at are standard in every production table
    # timezone.utc ensures we always store in UTC, never local time
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),  # auto-update on any change
        nullable=False,
    )

    def __repr__(self) -> str:
        # __repr__ is what prints when you do print(user) — useful for debugging
        return f"<User id={self.id} email={self.email} role={self.role}>"
