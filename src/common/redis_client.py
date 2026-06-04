"""Async Redis client — application-wide singleton.

Usage:
    from src.common.redis_client import get_redis

    redis = await get_redis()
    await redis.set("key", "value", ex=300)
    value = await redis.get("key")
"""

import redis.asyncio as aioredis

from src.config import settings

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Gracefully close the Redis connection (call on app shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
