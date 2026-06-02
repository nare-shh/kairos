import redis.asyncio as aioredis

from app.core.config import settings

# Module-level variable — holds the single Redis connection pool
# None initially; initialized when the app starts
_redis_client: aioredis.Redis | None = None


async def init_redis() -> None:
    """Called once at app startup to create the connection pool."""
    global _redis_client
    _redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,   # returns strings instead of bytes
    )


async def close_redis() -> None:
    """Called at app shutdown to cleanly close all connections."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()


def get_redis() -> aioredis.Redis:
    """
    Dependency injected into routes that need Redis.
    Raises immediately if Redis wasn't initialized — fails loud, not silent.
    """
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client
