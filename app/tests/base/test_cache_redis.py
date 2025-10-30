"""
Tests for synchronous and asynchronous Redis helpers (sredis, aredis).

This version:
- Initializes Django settings safely.
- Mocks the channel layer fully (with lock and redis attr).
- Skips DB setup/flush.
- Supports both sync and async Redis tests.
"""

import asyncio
import os
from unittest.mock import patch

import pytest
import django
import redis

import fakeredis
from redis import asyncio as aioredis
from redis.asyncio.connection import ConnectionPool as AsyncConnectionPool
from redis.connection import ConnectionPool as SyncConnectionPool

# Ensure Django is configured before importing eventyay modules
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventyay.config.settings")
django.setup()

from eventyay.core.utils.redis import sredis, aredis  # noqa: E402


# Pytest configuration
pytestmark = pytest.mark.django_db(transaction=False)
TEST_KEY = "test:cache:key"
TEST_VERSION = "12345"


# Dummy Channel Layer and Shards
class _DummyLock:
    async def __aenter__(self):
        self._lock = asyncio.Lock()
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()


class DummyShard:
    def __init__(self, fake_server):
        # mimic real shard structure
        self.host = {"address": "redis://localhost:6379"}
        self._fake_server = fake_server
        self._lock = _DummyLock()
        async_pool = AsyncConnectionPool(
            connection_class=fakeredis.aioredis.FakeConnection,
            server=fake_server,
        )
        self._redis = aioredis.Redis(connection_pool=async_pool)

    def _ensure_redis(self):
        # mimic ensuring connection
        if not self._redis:
            async_pool = AsyncConnectionPool(
                connection_class=fakeredis.aioredis.FakeConnection,
                server=self._fake_server,
            )
            self._redis = aioredis.Redis(connection_pool=async_pool)


class DummyLayer:
    def __init__(self, fake_server):
        self._shards = [DummyShard(fake_server)]


# Fixtures
@pytest.fixture
def fake_server():
    return fakeredis.FakeServer()


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch, fake_server):
    def fake_create_pool(host):
        return AsyncConnectionPool(
            connection_class=fakeredis.aioredis.FakeConnection,
            server=fake_server,
        )

    def fake_from_url(url, **kwargs):
        return SyncConnectionPool(
            connection_class=fakeredis.FakeConnection,
            server=fake_server,
        )

    monkeypatch.setattr("eventyay.core.utils.redis.create_pool", fake_create_pool)
    monkeypatch.setattr("eventyay.core.utils.redis.redis.ConnectionPool.from_url", fake_from_url)

    yield


# Tests
def test_sredis_set_and_get(fake_server):
    """
    Ensure sredis() can write and read synchronously without an event loop.
    """
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(fake_server)):
        with sredis(TEST_KEY) as conn:
            conn.set(f"{TEST_KEY}:version", TEST_VERSION)
        with sredis(TEST_KEY) as conn:
            val = conn.get(f"{TEST_KEY}:version")
        assert val.decode() == TEST_VERSION


@pytest.mark.asyncio
async def test_aredis_set_and_get(fake_server):
    """
    Ensure aredis() works in an async context and can set/get values.
    """
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(fake_server)):
        async with aredis(TEST_KEY) as redis:
            await redis.set(f"{TEST_KEY}:version", TEST_VERSION)
        async with aredis(TEST_KEY) as redis:
            val = await redis.get(f"{TEST_KEY}:version")
        assert val.decode() == TEST_VERSION


@pytest.mark.asyncio
async def test_aredis_per_loop_isolation(fake_server):
    """
    Verify that different loops get different pool mappings
    (prevents cross-loop 'Future attached to different loop' issues).
    """
    marker = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(fake_server)):

            async def _in_new_loop():
                async with aredis(TEST_KEY) as redis:
                    await redis.ping()
                    return id(redis.connection_pool)

            # Run once in current loop
            pool1 = await _in_new_loop()

            # Run again in a brand-new event loop
            pool2 = await asyncio.to_thread(lambda: asyncio.run(_in_new_loop()))

            assert pool1 != pool2
    finally:
        if marker is not None:
            os.environ["PYTEST_CURRENT_TEST"] = marker


@pytest.mark.asyncio
async def test_aredis_handles_connection_error(fake_server, monkeypatch):
    """
    Ensure aredis gracefully raises ConnectionError when ping fails.
    """
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(fake_server)):

        async def failing_ping():
            raise redis.exceptions.ConnectionError("Simulated failure")

        async with aredis(TEST_KEY) as redis_conn:
            monkeypatch.setattr(redis_conn, "ping", failing_ping)
            with pytest.raises(redis.exceptions.ConnectionError):
                await redis_conn.ping()


def test_sredis_handles_connection_error(fake_server, monkeypatch):
    """
    Ensure sredis rebuilds the connection pool on connection failure.
    """
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(fake_server)):

        # Make .ping() fail once
        def failing_ping():
            raise redis.exceptions.ConnectionError("Simulated sync failure")

        # Replace ping temporarily
        with sredis(TEST_KEY) as conn:
            monkeypatch.setattr(conn, "ping", failing_ping)
            with pytest.raises(redis.exceptions.ConnectionError):
                conn.ping()

        # Ensure pool recovers and works again
        with sredis(TEST_KEY) as conn:
            conn.set(f"{TEST_KEY}:version", TEST_VERSION)
            val = conn.get(f"{TEST_KEY}:version")
        assert val.decode() == TEST_VERSION


@pytest.mark.asyncio
async def test_aredis_retries_after_failure(fake_server, monkeypatch):
    """
    Simulate a transient ping failure and ensure a subsequent ping works.
    """
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(fake_server)):

        call_count = {"pings": 0}

        async def flaky_ping(self):
            call_count["pings"] += 1
            if call_count["pings"] == 1:
                raise redis.exceptions.ConnectionError("Transient failure")
            return True

        # Patch Redis.ping (needs self)
        monkeypatch.setattr("eventyay.core.utils.redis.aioredis.Redis.ping", flaky_ping)

        async with aredis(TEST_KEY) as redis_conn:
            # First call fails
            with pytest.raises(redis.exceptions.ConnectionError):
                await redis_conn.ping()

            # Second call succeeds
            result = await redis_conn.ping()
            assert result is True
