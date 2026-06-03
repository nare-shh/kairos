import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context
from dotenv import load_dotenv

# Load alembic logging config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Base.metadata knows every table
from app.db.session import Base       # noqa: E402
from app.models import category       # noqa: F401, E402
from app.models import event_store    # noqa: F401, E402
from app.models import order          # noqa: F401, E402
from app.models import product        # noqa: F401, E402
from app.models import user           # noqa: F401, E402

target_metadata = Base.metadata


def get_url() -> str:
    """
    Read DATABASE_URL from environment.
    Alembic uses psycopg2 (sync driver) — swap asyncpg for the sync driver.
    postgresql+asyncpg://...  →  postgresql://...
    """
    load_dotenv()
    url = os.getenv("DATABASE_URL", "")
    # Strip the asyncpg driver prefix — psycopg2 is the default sync driver
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def run_migrations_offline() -> None:
    """Generate SQL without connecting (for DBA review)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against the live database.
    Uses a plain synchronous psycopg2 engine — simple and reliable.
    No async needed here; migrations run once at startup, not in request paths.
    """
    engine = create_engine(
        get_url(),
        poolclass=pool.NullPool,  # no connection pooling for one-shot migrations
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
