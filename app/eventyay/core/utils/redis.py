import asyncio
import binascii
import os
import weakref
from contextlib import asynccontextmanager, contextmanager

import redis
from channels.layers import get_channel_layer
from channels_redis.utils import create_pool
from django.conf import settings
from redis import asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff


def consistent_hash(value):
    """
    Maps the value to a node value between 0 and 4095
    using CRC, then down to one of the ring nodes.
    """
    if isinstance(value, str):
        value = value.encode("utf8")
    bigval = binascii.crc32(value) & 0xFFF
    ring_divisor = 4096 / float(len(settings.REDIS_HOSTS))
    return int(bigval / ring_divisor)


_sync_pools = {}
_pools_by_loop = weakref.WeakKeyDictionary()


@asynccontextmanager
async def aredis(shard_key=None):
    shard_index = consistent_hash(shard_key) if shard_key else 0
    host = settings.REDIS_HOSTS[shard_index]

    if "PYTEST_CURRENT_TEST" in os.environ:
        shard = get_channel_layer()._shards[shard_index]
        async with shard._lock:
            shard._ensure_redis()
        yield shard._redis
        return

    loop = asyncio.get_running_loop()
    pool_map = _pools_by_loop.get(loop)
    if pool_map is None:
        pool_map = {}
        _pools_by_loop[loop] = pool_map

    pool = pool_map.get(shard_index)
    if pool is None:
        pool = create_pool(host)
        pool_map[shard_index] = pool

    def _make_conn(active_pool):
        return aioredis.Redis(
            connection_pool=active_pool,
            retry=Retry(ExponentialBackoff(), 3),
            retry_on_error=[redis.exceptions.ConnectionError],
            retry_on_timeout=True,
        )

    async def _connect_with_retry(active_pool):
        conn = _make_conn(active_pool)
        try:
            await conn.ping()
        except redis.exceptions.ConnectionError:
            await conn.aclose()
            return None
        return conn

    conn = await _connect_with_retry(pool)
    if conn is None:
        await pool.aclose()
        pool = create_pool(host)
        pool_map[shard_index] = pool
        conn = await _connect_with_retry(pool)
        if conn is None:
            conn = _make_conn(pool)
            await conn.ping()

    try:
        yield conn
    finally:
        await conn.aclose()


def _build_sync_pool(host_cfg):
    if isinstance(host_cfg, dict):
        address = host_cfg.get("address")
        if isinstance(address, str):
            return redis.ConnectionPool.from_url(address)
        if isinstance(address, (tuple, list)):
            h, p = address
            return redis.ConnectionPool.from_url(f"redis://{h}:{p}")
        return redis.ConnectionPool(**host_cfg)
    if isinstance(host_cfg, str):
        return redis.ConnectionPool.from_url(host_cfg)
    if isinstance(host_cfg, (tuple, list)):
        h, p = host_cfg
        return redis.ConnectionPool.from_url(f"redis://{h}:{p}")
    return redis.ConnectionPool(**host_cfg)


@contextmanager
def sredis(shard_key=None):
    shard_index = consistent_hash(shard_key) if shard_key else 0
    try:
        shard = get_channel_layer()._shards[shard_index]
        host_cfg = shard.host
    except Exception:
        cfg_hosts = settings.CHANNEL_LAYERS["default"]["CONFIG"]["hosts"]
        host_cfg = cfg_hosts[shard_index if shard_index < len(cfg_hosts) else 0]

    pool = _sync_pools.get(shard_index)
    if pool is None:
        pool = _build_sync_pool(host_cfg)
        _sync_pools[shard_index] = pool

    conn = redis.Redis(connection_pool=pool)
    try:
        conn.ping()
    except redis.exceptions.ConnectionError:
        conn.close()
        pool.disconnect()
        pool = _build_sync_pool(host_cfg)
        _sync_pools[shard_index] = pool
        conn = redis.Redis(connection_pool=pool)
        conn.ping()

    try:
        yield conn
    finally:
        conn.close()


async def flush_aredis_pool():
    global _pools_by_loop, _sync_pools
    for pool_map in list(_pools_by_loop.values()):
        for pool in pool_map.values():
            await pool.aclose()
    _pools_by_loop = weakref.WeakKeyDictionary()
    for pool in _sync_pools.values():
        pool.disconnect()
    _sync_pools = {}
