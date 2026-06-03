import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # slug = URL-friendly version of the name
    # "Electronics" → "electronics"
    # "Men's Clothing" → "mens-clothing"
    # Used in URLs: /products?category=mens-clothing
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Self-referencing foreign key — a category can have a parent category
    # This creates a tree structure:
    #   Electronics (parent_id = None)
    #   └── Phones   (parent_id = Electronics.id)
    #       └── Smartphones (parent_id = Phones.id)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships — SQLAlchemy loads related objects automatically
    # "children" → all sub-categories of this one
    # back_populates="parent" → each child has a .parent reference back
    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        foreign_keys=[parent_id],
    )
    parent: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="children",
        foreign_keys=[parent_id],
        remote_side="Category.id",
    )

    # products → all products in this category (defined via back_populates in Product)
    products: Mapped[list["Product"]] = relationship(  # noqa: F821
        "Product", back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name}>"
