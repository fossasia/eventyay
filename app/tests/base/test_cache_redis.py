import asyncio
import os
from unittest.mock import patch

import pytest
import django
import redis
import fakeredis

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eventyay.config.settings")
django.setup()

from eventyay.core.utils.redis import sredis, aredis  # noqa: E402

pytestmark = pytest.mark.django_db(transaction=False)
TEST_KEY = "test:cache:key"
TEST_VERSION = "12345"


class _DummyLock:
    async def __aenter__(self):
        self._lock = asyncio.Lock()
        await self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()


class DummyShard:
    def __init__(self, fake_async):
        self._lock = _DummyLock()
        self._redis = fake_async

    def _ensure_redis(self):
        pass


class DummyLayer:
    def __init__(self, fake_async):
        self._shards = [DummyShard(fake_async)]


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    shared_server = fakeredis.FakeServer()
    fake_sync = fakeredis.FakeStrictRedis(server=shared_server)
    fake_async = fakeredis.FakeAsyncRedis(server=shared_server)

    def fake_sync_from_url(url, *a, **kw):
        return fake_sync

    def fake_async_from_url(url, *a, **kw):
        return fake_async

    monkeypatch.setattr("eventyay.core.utils.redis.redis.from_url", fake_sync_from_url)
    monkeypatch.setattr("eventyay.core.utils.redis.redis.asyncio.from_url", fake_async_from_url)

    return fake_async


def _maybe_await(result):
    if asyncio.iscoroutine(result):
        return asyncio.get_event_loop().run_until_complete(result)
    return result


def test_sredis_set_and_get(mock_redis):
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(mock_redis)):
        with sredis(TEST_KEY) as conn:
            _maybe_await(conn.set(f"{TEST_KEY}:version", TEST_VERSION))
        with sredis(TEST_KEY) as conn:
            val = _maybe_await(conn.get(f"{TEST_KEY}:version"))
        assert val.decode() == TEST_VERSION


@pytest.mark.asyncio
async def test_aredis_set_and_get(mock_redis):
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(mock_redis)):
        async with aredis(TEST_KEY) as redis_conn:
            await redis_conn.set(f"{TEST_KEY}:version", TEST_VERSION)
        async with aredis(TEST_KEY) as redis_conn:
            val = await redis_conn.get(f"{TEST_KEY}:version")
        assert val.decode() == TEST_VERSION


@pytest.mark.asyncio
async def test_aredis_handles_connection_error(monkeypatch, mock_redis):
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(mock_redis)):

        async def failing_ping(self):
            raise redis.exceptions.ConnectionError("Simulated async failure")

        monkeypatch.setattr("eventyay.core.utils.redis.redis.asyncio.Redis.ping", failing_ping)

        async with aredis(TEST_KEY) as conn:
            with pytest.raises(redis.exceptions.ConnectionError):
                await conn.ping()


def test_sredis_handles_connection_error(monkeypatch, mock_redis):
    with patch("eventyay.core.utils.redis.get_channel_layer", return_value=DummyLayer(mock_redis)):

        def failing_ping():
            raise redis.exceptions.ConnectionError("Simulated sync failure")

        with sredis(TEST_KEY) as conn:
            monkeypatch.setattr(conn, "ping", failing_ping)
            with pytest.raises(redis.exceptions.ConnectionError):
                conn.ping()
