from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# create_async_engine creates a connection pool to PostgreSQL
# pool_pre_ping=True: tests each connection before using it (handles dropped connections)
# echo=True in dev: prints every SQL query to console so you can see what's happening
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

# async_sessionmaker is a factory — calling AsyncSessionLocal() gives you a session
# expire_on_commit=False: keeps objects usable after a commit (important for async)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Base class that all our database models will inherit from
# SQLAlchemy uses this to know which classes are database tables
class Base(DeclarativeBase):
    pass


# Dependency — FastAPI calls this to inject a DB session into each request
# "yield" makes this a generator: code before yield = setup, after yield = cleanup
# The session is automatically closed after each request, even if an error occurs
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
