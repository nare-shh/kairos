"""
Seed Data
═════════
    python -m app.seed                                  # demo users, categories, products
    python -m app.seed create-admin EMAIL PASSWORD      # create (or promote) an admin

Idempotent — safe to run repeatedly: existing users, categories and SKUs are skipped.
Products are created through ProductService, so each one gets its ProductCreated event.

Demo accounts (development only — never seed these into production):
    admin@kairos.dev     / Admin1234     admin   (manage categories, fulfil orders)
    naresh@kairos.dev    / Kairos123     seller  (owns the demo catalog)
    customer@kairos.dev  / Customer123   customer
"""

import argparse
import asyncio
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models import event_store as _event_models  # noqa: F401  (register all tables)
from app.models import order as _order_models        # noqa: F401
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.schemas.category import CategoryCreateRequest
from app.schemas.product import ProductCreateRequest
from app.services.category_service import CategoryService
from app.services.product_service import ProductService

DEMO_USERS = [
    # email, password, full name, role
    ("admin@kairos.dev", "Admin1234", "Kairos Admin", "admin"),
    ("naresh@kairos.dev", "Kairos123", "Naresh S", "seller"),
    ("customer@kairos.dev", "Customer123", "Demo Customer", "customer"),
]

CATEGORIES = [
    # name, parent name, description
    ("Electronics", None, "Gadgets, wearables and accessories"),
    ("Audio", "Electronics", "Headphones, earbuds and speakers"),
    ("Footwear", None, "Running, hiking and everyday shoes"),
    ("Home & Kitchen", None, "Cookware, coffee and home essentials"),
    ("Books", None, "Engineering and business reads"),
]

PRODUCTS = [
    {
        "name": "Aurora Wireless Earbuds", "sku": "AUR-EB-01", "category": "Audio",
        "base": "2499", "min": "1999", "max": "3299", "stock": 40,
        "description": "Compact earbuds with 30-hour battery life and a pocketable charging case.",
        "attributes": {"color": "Midnight Black", "battery": "30h", "bluetooth": "5.3"},
    },
    {
        "name": "Nimbus Noise-Cancelling Headphones", "sku": "NIM-HP-02", "category": "Audio",
        "base": "7999", "min": "6499", "max": "9999", "stock": 15,
        "description": "Over-ear headphones with adaptive noise cancellation and plush memory-foam cushions.",
        "attributes": {"color": "Silver", "battery": "40h", "anc": "Adaptive"},
    },
    {
        "name": "Pulse Smartwatch S2", "sku": "PUL-SW-02", "category": "Electronics",
        "base": "4999", "min": "3999", "max": "6499", "stock": 25,
        "description": "Fitness smartwatch with heart-rate, SpO2 and 10-day battery.",
        "attributes": {"display": "1.4in AMOLED", "water_resistance": "5 ATM"},
    },
    {
        "name": "Volt 20000mAh Power Bank", "sku": "VLT-PB-20", "category": "Electronics",
        "base": "1499", "min": "1199", "max": "1999", "stock": 60,
        "description": "Fast-charging power bank with USB-C PD and two USB-A ports.",
        "attributes": {"capacity": "20000mAh", "output": "22.5W"},
    },
    {
        "name": "Lumen 4K Action Camera", "sku": "LUM-AC-4K", "category": "Electronics",
        "base": "12999", "min": "10999", "max": "15999", "stock": 6, "threshold": 8,
        "description": "Waterproof 4K60 action camera with electronic image stabilisation.",
        "attributes": {"resolution": "4K60", "waterproof": "10m"},
    },
    {
        "name": "Stride Runner Pro", "sku": "STR-RN-PRO", "category": "Footwear",
        "base": "3999", "min": "3299", "max": "4999", "stock": 30,
        "description": "Lightweight daily trainer with responsive foam and breathable mesh.",
        "attributes": {"sizes": "UK 6-11", "drop": "8mm"},
    },
    {
        "name": "Trailblazer Hiking Boots", "sku": "TRL-HB-01", "category": "Footwear",
        "base": "5499", "min": "4499", "max": "6999", "stock": 5,
        "description": "Waterproof leather hiking boots with a grippy lugged outsole.",
        "attributes": {"sizes": "UK 6-12", "waterproof": "Yes"},
    },
    {
        "name": "Brew Master Pour-Over Kit", "sku": "BRW-PO-01", "category": "Home & Kitchen",
        "base": "1899", "min": "1499", "max": "2499", "stock": 20,
        "description": "Glass dripper, carafe and reusable steel filter for clean, bright coffee.",
        "attributes": {"capacity": "600ml", "material": "Borosilicate glass"},
    },
    {
        "name": "Cast Iron Skillet 10in", "sku": "CST-SK-10", "category": "Home & Kitchen",
        "base": "1299", "min": "999", "max": "1699", "stock": 35,
        "description": "Pre-seasoned cast iron skillet that goes from stovetop to oven.",
        "attributes": {"diameter": "10in", "weight": "2.3kg"},
    },
    {
        "name": "Aroma Diffuser Mini", "sku": "ARM-DF-MN", "category": "Home & Kitchen",
        "base": "899", "min": "699", "max": "1199", "stock": 50,
        "description": "Ultrasonic essential-oil diffuser with a soft night light.",
        "attributes": {"runtime": "8h", "tank": "150ml"},
    },
    {
        "name": "Systems Design Field Guide", "sku": "BK-SDF-01", "category": "Books",
        "base": "699", "min": "549", "max": "899", "stock": 45,
        "description": "A practical guide to building scalable, reliable backend systems.",
        "attributes": {"format": "Paperback", "pages": "412"},
    },
    {
        "name": "The Pricing Playbook", "sku": "BK-PRC-01", "category": "Books",
        "base": "499", "min": "399", "max": "649", "stock": 3, "threshold": 5,
        "description": "How modern businesses set, test and adapt their prices.",
        "attributes": {"format": "Paperback", "pages": "236"},
    },
]


async def _get_or_create_user(db, email: str, password: str, full_name: str, role: str) -> tuple[User, bool]:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user:
        return user, False
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    await db.flush()
    return user, True


async def seed_demo() -> None:
    async with AsyncSessionLocal() as db:
        users = {}
        for email, password, full_name, role in DEMO_USERS:
            user, created = await _get_or_create_user(db, email, password, full_name, role)
            users[role] = user
            print(f"  user      {email:<22} {'created' if created else 'exists'}")

        category_ids: dict[str, uuid.UUID] = {}
        categories = CategoryService(db)
        for name, parent, description in CATEGORIES:
            existing = (await db.execute(select(Category).where(Category.name == name))).scalar_one_or_none()
            if existing:
                category_ids[name] = existing.id
                print(f"  category  {name:<22} exists")
                continue
            created = await categories.create(CategoryCreateRequest(
                name=name, description=description, parent_id=category_ids.get(parent),
            ))
            category_ids[name] = created.id
            print(f"  category  {name:<22} created")

        products = ProductService(db)
        for item in PRODUCTS:
            exists = (await db.execute(select(Product.id).where(Product.sku == item["sku"]))).scalar_one_or_none()
            if exists:
                print(f"  product   {item['sku']:<22} exists")
                continue
            await products.create_product(
                ProductCreateRequest(
                    name=item["name"],
                    sku=item["sku"],
                    description=item["description"],
                    base_price=Decimal(item["base"]),
                    min_price=Decimal(item["min"]),
                    max_price=Decimal(item["max"]),
                    stock_quantity=item["stock"],
                    low_stock_threshold=item.get("threshold", 10),
                    category_id=category_ids[item["category"]],
                    attributes=item["attributes"],
                ),
                users["seller"],
            )
            print(f"  product   {item['sku']:<22} created")

        await db.commit()

    print("\nDemo accounts:")
    for email, password, _, role in DEMO_USERS:
        print(f"  {role:<9} {email:<22} {password}")


async def create_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        user, created = await _get_or_create_user(db, email, password, "Administrator", "admin")
        if not created and user.role != "admin":
            user.role = "admin"
            print(f"Promoted existing user {email} to admin (password unchanged)")
        elif created:
            print(f"Created admin {email}")
        else:
            print(f"{email} is already an admin")
        await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kairos seed data")
    sub = parser.add_subparsers(dest="command")
    admin = sub.add_parser("create-admin", help="create or promote an admin account")
    admin.add_argument("email")
    admin.add_argument("password")
    args = parser.parse_args()

    async def run() -> None:
        try:
            if args.command == "create-admin":
                await create_admin(args.email, args.password)
            else:
                print("Seeding Kairos demo data...")
                await seed_demo()
        finally:
            await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
