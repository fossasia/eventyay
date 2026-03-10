import asyncio
import os
from contextlib import asynccontextmanager, contextmanager

import redis
from django.conf import settings
from channels.layers import get_channel_layer


@contextmanager
def sredis(shard_key=None):
    """
    Synchronous Redis connection using settings.REDIS_URL.
    Closes after use; no connection pool required.
    """
    if "PYTEST_CURRENT_TEST" in os.environ:
        shard = get_channel_layer()._shards[0]
        conn = shard._redis
        yield conn
        return

    conn = redis.from_url(settings.REDIS_URL)
    try:
        yield conn
    finally:
        conn.close()


@asynccontextmanager
async def aredis(shard_key=None):
    """
    Asynchronous Redis connection using redis-py’s asyncio interface.
    """
    if "PYTEST_CURRENT_TEST" in os.environ:
        shard = get_channel_layer()._shards[0]
        async with shard._lock:
            shard._ensure_redis()
        yield shard._redis
        return

    conn = redis.asyncio.from_url(settings.REDIS_URL)
    try:
        await conn.ping()
        yield conn
    finally:
        await conn.close()


async def flush_aredis_pool():
    """No-op, left for backward compatibility."""
    pass
