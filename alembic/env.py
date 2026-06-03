"""
alembic/env.py — The brain of Alembic.

This file runs every time you execute an alembic command.
It tells Alembic:
  1. How to connect to your database
  2. Which models to inspect for schema changes
  3. Whether to run migrations online (against a live DB) or offline (generates SQL)

Two modes:
──────────
  Online mode:  Alembic connects to your DB and runs migrations directly
  Offline mode: Alembic generates raw SQL you can review and run manually
                Useful for DBAs who need to approve migrations before they run
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# This imports Alembic's logging config from alembic.ini
config = context.config

# Setup Python logging as configured in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import your models ────────────────────────────────────────────────────────
# CRITICAL: You must import ALL your models here.
# Alembic compares Base.metadata (all your model definitions) against
# the actual database schema to detect what changed.
# If you don't import a model, Alembic won't know it exists.
from app.db.session import Base  # noqa: E402

# Import every model so Base.metadata knows about all tables
from app.models import category   # noqa: F401, E402
from app.models import event_store  # noqa: F401, E402
from app.models import order        # noqa: F401, E402
from app.models import product      # noqa: F401, E402
from app.models import user         # noqa: F401, E402

# target_metadata tells Alembic what your schema SHOULD look like
# It will compare this against the current DB and generate the diff
target_metadata = Base.metadata


# ── Get the database URL ──────────────────────────────────────────────────────
def get_url() -> str:
    """
    Read DATABASE_URL from the environment.
    Falls back to alembic.ini if not set (shouldn't happen in practice).

    Important: Alembic uses a SYNC driver for migrations even though our app
    uses async. We swap asyncpg for psycopg2 here.
    asyncpg  → used by the running app (fast, async)
    psycopg2 → used by alembic migrations (sync, simpler for migrations)
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    url = os.getenv("DATABASE_URL", "")

    # Alembic needs a synchronous driver — swap asyncpg for psycopg2
    # "postgresql+asyncpg://..." → "postgresql+psycopg2://..."
    # If psycopg2 not installed, use: "postgresql://..."
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


# ── Offline mode ──────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL statements without connecting to the database.
    Output can be reviewed and applied manually by a DBA.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # compare_type=True: detect column type changes (e.g., VARCHAR(100) → VARCHAR(255))
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ───────────────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # compare_server_default=True: detect default value changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations asynchronously.
    Creates a temporary sync connection from our async engine config.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # NullPool: don't maintain a connection pool for migrations
        # Each migration run gets one connection and drops it
        # This prevents connection leaks in CI/CD pipelines
    )

    async with connectable.connect() as connection:
        # run_sync wraps our sync migration logic in the async context
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    asyncio.run(run_async_migrations())


# ── Main entry point ──────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
