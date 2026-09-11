"""
Shared test fixtures
════════════════════
- Unit tests (pricing math, Redis scoring, trending) need nothing external.
- API tests need PostgreSQL. They use TEST_DATABASE_URL
    (default: postgresql+asyncpg://kairos_user:kairos_pass@localhost:5432/kairos_test)
  The database is created if missing, migrated with Alembic, and truncated
  before every test. API tests are SKIPPED when PostgreSQL is unreachable.
- Redis is always an in-memory fake (fakeredis) — no Redis server needed.
"""

import os
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://kairos_user:kairos_pass@localhost:5432/kairos_test",
)

# Must run before any `app` import — Settings() reads the environment at import time.
# DATABASE_URL is overridden so the tests can never touch your dev database.
os.environ.update({
    "DATABASE_URL": TEST_DATABASE_URL,
    "APP_ENV": "test",
    "DEBUG": "true",
    "SECRET_KEY": "test-secret-key-not-for-production",
    "KAFKA_ENABLED": "false",
    "REPRICE_INTERVAL_SECONDS": "0",
    "STRIPE_SECRET_KEY": "",
    "STRIPE_WEBHOOK_SECRET": "",
})

from urllib.parse import urlsplit, urlunsplit  # noqa: E402

import fakeredis  # noqa: E402
import httpx  # noqa: E402
import psycopg2  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402
from app.db import redis as redis_module  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TABLES = "order_items, orders, event_store, products, categories, users"

# Tests log in many times from the same client address
limiter.enabled = False


@pytest.fixture(scope="session")
def database() -> str:
    """Create the test database if needed and migrate it to head (once per run)."""
    sync_url = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    parts = urlsplit(sync_url)
    db_name = parts.path.lstrip("/")
    maintenance_url = urlunsplit(parts._replace(path="/postgres"))

    try:
        conn = psycopg2.connect(maintenance_url, connect_timeout=3)
    except psycopg2.OperationalError as e:
        pytest.skip(f"PostgreSQL not reachable for API tests: {str(e).strip()}")

    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()

    # Run the real migrations — this also tests them
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def fake_redis(monkeypatch):
    """A fresh in-memory Redis per test, installed as the app's Redis client."""
    client = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    monkeypatch.setattr(redis_module, "_redis_client", client)
    yield client
    await client.aclose()


@pytest.fixture
async def client(database, fake_redis):
    """HTTP client for the app, on an empty database."""
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http

    # Pooled connections belong to this test's event loop — drop them
    await engine.dispose()
