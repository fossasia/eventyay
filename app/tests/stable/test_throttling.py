"""
Tests for API throttling: Block404Middleware, PublicStreamThrottle,
PublicScheduleThrottle, and EventyayAnonRateThrottle / EventyayUserRateThrottle.

Uses LocMemCache and fakeredis isolation (override_settings) to ensure throttle
state never bleeds between tests and that the tests can run without a running
Redis instance (with an optional TEST_REDIS_URL switch for live Redis checks).
"""

import logging
import os
import uuid

import fakeredis
import pytest
import redis
from django.core.cache import caches
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.redis import RedisCache as DjangoRedisCache
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from redis.exceptions import ResponseError

from eventyay.middleware import block_404
from eventyay.middleware.block_404 import _API_PATH_PREFIX, Block404Middleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-throttle-cache',
    }
}


class _AnonymousUser:
    """Minimal stand-in for AnonymousUser — avoids importing Django auth."""
    is_authenticated = False
    pk = None


def _anon_user():
    """Return a fresh anonymous-user stub for attaching to RequestFactory requests."""
    return _AnonymousUser()



def _make_get_response(status_code=200):
    """Return a simple WSGI callable that always returns a fixed status."""
    def get_response(request):
        return HttpResponse(status=status_code)
    return get_response


# ---------------------------------------------------------------------------
# Block404Middleware tests
# ---------------------------------------------------------------------------

class TestBlock404Middleware:

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_non_api_path_is_never_blocked(self):
        """404s on non-API paths must never trigger the 429 guard."""
        from django.core.cache import caches
        caches['default'].clear()

        from eventyay.middleware.block_404 import Block404Middleware
        middleware = Block404Middleware(_make_get_response(404))
        factory = RequestFactory()

        for _ in range(50):
            request = factory.get('/some-html-page/')
            request.user = _anon_user()
            response = middleware(request)
            assert response.status_code == 404, "Non-API 404 should never be blocked"

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_api_404s_below_limit_pass_through(self):
        """The first MAX_404_PER_MINUTE API 404s should return 404, not 429."""
        from django.core.cache import caches
        caches['default'].clear()

        from eventyay.middleware.block_404 import _API_PATH_PREFIX, Block404Middleware
        middleware = Block404Middleware(_make_get_response(404))
        factory = RequestFactory()

        for i in range(Block404Middleware.MAX_404_PER_MINUTE):
            request = factory.get(f'{_API_PATH_PREFIX}v1/nonexistent/')
            request.user = _anon_user()
            response = middleware(request)
            assert response.status_code == 404, f"Request {i + 1} should still be 404"

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_api_404s_above_limit_return_429(self):
        """After MAX_404_PER_MINUTE+1 API 404s, subsequent requests should return 429."""
        from django.core.cache import caches
        caches['default'].clear()

        from eventyay.middleware.block_404 import _API_PATH_PREFIX, Block404Middleware
        middleware = Block404Middleware(_make_get_response(404))
        factory = RequestFactory()

        # Exhaust the limit
        for _ in range(Block404Middleware.MAX_404_PER_MINUTE + 1):
            request = factory.get(f'{_API_PATH_PREFIX}v1/nonexistent/')
            request.user = _anon_user()
            middleware(request)

        # Next request should be throttled
        request = factory.get(f'{_API_PATH_PREFIX}v1/nonexistent/')
        request.user = _anon_user()
        response = middleware(request)
        assert response.status_code == 429

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_429_includes_retry_after_header(self):
        """The 429 response must include a Retry-After header."""
        from django.core.cache import caches
        caches['default'].clear()

        from eventyay.middleware.block_404 import _API_PATH_PREFIX, Block404Middleware
        middleware = Block404Middleware(_make_get_response(404))
        factory = RequestFactory()

        for _ in range(Block404Middleware.MAX_404_PER_MINUTE + 1):
            request = factory.get(f'{_API_PATH_PREFIX}v1/nonexistent/')
            request.user = _anon_user()
            middleware(request)

        request = factory.get(f'{_API_PATH_PREFIX}v1/nonexistent/')
        request.user = _anon_user()
        response = middleware(request)
        assert response.status_code == 429
        assert response['Retry-After'] == Block404Middleware.RETRY_AFTER_SECONDS

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_200_responses_do_not_increment_counter(self):
        """Successful API responses must not increment the 404 counter."""
        from django.core.cache import caches
        caches['default'].clear()

        from eventyay.middleware.block_404 import _API_PATH_PREFIX, Block404Middleware
        middleware = Block404Middleware(_make_get_response(200))
        factory = RequestFactory()

        for _ in range(Block404Middleware.MAX_404_PER_MINUTE + 10):
            request = factory.get(f'{_API_PATH_PREFIX}v1/rooms/')
            request.user = _anon_user()
            response = middleware(request)
            assert response.status_code == 200

    def test_authenticated_user_keyed_by_user_id(self):
        """Authenticated users must be keyed by user ID, not IP."""
        from eventyay.middleware.block_404 import Block404Middleware

        class FakeUser:
            is_authenticated = True
            pk = 1

        class FakeRequest:
            user = FakeUser()
            auth = None

        class FakeUser2:
            is_authenticated = True
            pk = 2

        class FakeRequest2:
            user = FakeUser2()
            auth = None

        key1 = Block404Middleware._cache_key(FakeRequest())
        key2 = Block404Middleware._cache_key(FakeRequest2())
        assert key1 != key2
        assert 'user:1' in key1
        assert 'user:2' in key2

    def test_anonymous_keyed_by_ip(self):
        """Anonymous requests must be keyed by IP address."""
        from eventyay.middleware.block_404 import Block404Middleware
        factory = RequestFactory()
        request = factory.get('/api/v1/', REMOTE_ADDR='1.2.3.4')

        class AnonUser:
            is_authenticated = False

        request.user = AnonUser()
        request.auth = None
        key = Block404Middleware._cache_key(request)
        assert 'ip:' in key


# ---------------------------------------------------------------------------
# Throttle class unit tests
# ---------------------------------------------------------------------------

class TestEventyayAnonRateThrottle:

    def test_skips_authenticated_user(self):
        """Anon throttle must return None (skip) for authenticated users."""
        from eventyay.api.throttles import EventyayAnonRateThrottle
        throttle = EventyayAnonRateThrottle()
        factory = RequestFactory()
        request = factory.get('/api/v1/')

        class AuthUser:
            is_authenticated = True

        request.user = AuthUser()
        request.auth = None
        assert throttle.get_cache_key(request, view=None) is None

    def test_skips_token_auth(self):
        """Anon throttle must return None (skip) when request.auth is set."""
        from eventyay.api.throttles import EventyayAnonRateThrottle
        throttle = EventyayAnonRateThrottle()
        factory = RequestFactory()
        request = factory.get('/api/v1/')

        class AnonUser:
            is_authenticated = False

        request.user = AnonUser()
        request.auth = object()  # any truthy value
        assert throttle.get_cache_key(request, view=None) is None

    def test_applies_to_anonymous(self):
        """Anon throttle must return a cache key for truly anonymous requests."""
        from eventyay.api.throttles import EventyayAnonRateThrottle
        throttle = EventyayAnonRateThrottle()
        factory = RequestFactory()
        request = factory.get('/api/v1/')

        class AnonUser:
            is_authenticated = False

        request.user = AnonUser()
        request.auth = None
        key = throttle.get_cache_key(request, view=None)
        assert key is not None


class TestEventyayUserRateThrottle:

    def test_keyed_on_user_pk(self):
        """User throttle must use user PK as identity."""
        from eventyay.api.throttles import EventyayUserRateThrottle
        throttle = EventyayUserRateThrottle()
        factory = RequestFactory()
        request = factory.get('/api/v1/')

        class AuthUser:
            is_authenticated = True
            pk = 42

        request.user = AuthUser()
        request.auth = None
        key = throttle.get_cache_key(request, view=None)
        assert '42' in key

    def test_keyed_on_token_type_and_pk(self):
        """User throttle must use token type + pk for TeamAPIToken / Device."""
        from eventyay.api.throttles import EventyayUserRateThrottle

        class FakeTeamToken:
            pk = 99

        class AnonUser:
            is_authenticated = False

        throttle = EventyayUserRateThrottle()
        factory = RequestFactory()
        request = factory.get('/api/v1/')
        request.user = AnonUser()
        request.auth = FakeTeamToken()
        key = throttle.get_cache_key(request, view=None)
        assert 'FakeTeamToken' in key
        assert '99' in key

    def test_returns_none_for_anonymous(self):
        """User throttle must return None for fully anonymous requests."""
        from eventyay.api.throttles import EventyayUserRateThrottle

        class AnonUser:
            is_authenticated = False

        throttle = EventyayUserRateThrottle()
        factory = RequestFactory()
        request = factory.get('/api/v1/')
        request.user = AnonUser()
        request.auth = None
        assert throttle.get_cache_key(request, view=None) is None


class TestPublicStreamThrottle:

    def test_scope(self):
        """PublicStreamThrottle must use the public_stream scope."""
        from eventyay.api.throttles import PublicStreamThrottle
        assert PublicStreamThrottle.scope == 'public_stream'

    def test_inherits_anon_behaviour(self):
        """PublicStreamThrottle must skip authenticated requests (inherited)."""
        from eventyay.api.throttles import PublicStreamThrottle

        class AuthUser:
            is_authenticated = True

        throttle = PublicStreamThrottle()
        factory = RequestFactory()
        request = factory.get('/api/v1/')
        request.user = AuthUser()
        request.auth = None
        assert throttle.get_cache_key(request, view=None) is None


class TestPublicScheduleThrottle:

    def test_scope(self):
        """PublicScheduleThrottle must use the public_schedule scope."""
        from eventyay.api.throttles import PublicScheduleThrottle
        assert PublicScheduleThrottle.scope == 'public_schedule'


class TestThrottleSettings:

    def test_global_throttle_excludes_ip_anon(self):
        from django.conf import settings

        classes = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES']
        assert 'EventyayAnonRateThrottle' not in classes
        assert 'eventyay.api.throttles.EventyayUserRateThrottle' in classes


# ---------------------------------------------------------------------------
# Block404Middleware Redis TTL & atomic increment tests
# ---------------------------------------------------------------------------


def _build_redis_cache_settings(backend_mode: str, key_prefix: str) -> dict:
    if backend_mode == 'live':
        redis_url = os.environ.get('TEST_REDIS_URL')
        if not redis_url:
            pytest.skip('TEST_REDIS_URL not set')
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.redis.RedisCache',
                'LOCATION': redis_url,
                'KEY_PREFIX': key_prefix,
            }
        }

    server = fakeredis.FakeServer()
    return {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': 'redis://localhost:6379/0',
            'KEY_PREFIX': key_prefix,
            'OPTIONS': {
                'connection_class': fakeredis.FakeRedisConnection,
                'server': server,
            },
        }
    }


def _cleanup_prefixed_keys(cache, key_prefix: str) -> None:
    made_probe = cache.make_and_validate_key('probe')
    client = cache._cache.get_client(made_probe, write=True)
    keys = list(client.scan_iter(match=f'{key_prefix}:*'))
    if keys:
        client.delete(*keys)


def _make_identity_request(identity_kind: str, path: str = f'{_API_PATH_PREFIX}v1/rooms/'):
    factory = RequestFactory()
    request = factory.get(path, REMOTE_ADDR='198.51.100.42')
    if identity_kind == 'user':

        class AuthUser:
            is_authenticated = True
            pk = 138

        request.user = AuthUser()
        request.auth = None
    elif identity_kind == 'token':

        class FakeToken:
            pk = 77

        request.user = _anon_user()
        request.auth = FakeToken()
    else:
        request.user = _anon_user()
        request.auth = None
    return request


@pytest.fixture(autouse=True)
def _reset_block404_redis_flags():
    block_404._redis_state.expire_nx_supported = None
    block_404._redis_state.missing_client_warned = False
    yield
    block_404._redis_state.expire_nx_supported = None
    block_404._redis_state.missing_client_warned = False


@pytest.fixture(params=['fakeredis', 'live'])
def redis_cache_env(request):
    key_prefix = f'test-404-{uuid.uuid4().hex}'
    caches_cfg = _build_redis_cache_settings(request.param, key_prefix)
    with override_settings(CACHES=caches_cfg):
        cache = caches[Block404Middleware.CACHE_ALIAS]
        try:
            yield cache
        finally:
            _cleanup_prefixed_keys(cache, key_prefix)


@pytest.fixture
def fakeredis_cache():
    key_prefix = f'test-404-{uuid.uuid4().hex}'
    caches_cfg = _build_redis_cache_settings('fakeredis', key_prefix)
    with override_settings(CACHES=caches_cfg):
        cache = caches[Block404Middleware.CACHE_ALIAS]
        try:
            yield cache
        finally:
            _cleanup_prefixed_keys(cache, key_prefix)


class _FutureDjangoRedisCache(DjangoRedisCache):
    def __init__(self, server, params):
        super().__init__(server, params)
        self._backend_impl = super()._cache

    @property
    def _cache(self):
        raise AttributeError('_cache removed in future Django')

    def get(self, key, default=None, version=None):
        return self._backend_impl.get(self.make_and_validate_key(key, version=version), default)

    def add(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        return self._backend_impl.add(
            self.make_and_validate_key(key, version=version),
            value,
            self.get_backend_timeout(timeout),
        )

    def incr(self, key, delta=1, version=None):
        return self._backend_impl.incr(self.make_and_validate_key(key, version=version), delta)


class TestBlock404MiddlewareRedis:
    def test_two_get_client_calls_share_same_fakeserver(self, fakeredis_cache):
        """Distinct get_client() instances must share the same FakeServer state and TTLs."""
        made_key = fakeredis_cache.make_and_validate_key('404_counter:user:138')
        client_one = fakeredis_cache._cache.get_client(made_key, write=True)
        client_two = fakeredis_cache._cache.get_client(made_key, write=True)
        assert client_one is not client_two

        client_one.set(made_key, 42, ex=60)
        assert client_two.get(made_key) == b'42'
        assert 0 < client_two.ttl(made_key) <= 60

    def test_increment_on_missing_key_sets_positive_ttl(self, redis_cache_env):
        """_increment on a missing key must return 1 and set a 60s TTL."""
        cache = redis_cache_env
        key = '404_counter:user:138'
        made_key = cache.make_and_validate_key(key)
        client = cache._cache.get_client(made_key, write=True)

        assert Block404Middleware._increment(cache, key) == 1
        assert client.get(made_key) == b'1'
        assert 0 < client.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

        middleware = Block404Middleware(_make_get_response(404))
        request = _make_identity_request('user')
        req_key = Block404Middleware._cache_key(request)
        made_req_key = cache.make_and_validate_key(req_key)
        client.delete(made_req_key)

        response = middleware(request)
        assert response.status_code == 404
        assert client.get(made_req_key) == b'1'
        assert 0 < client.ttl(made_req_key) <= Block404Middleware.WINDOW_SECONDS

    @pytest.mark.parametrize('identity_kind', ['user', 'token', 'ip'])
    def test_stuck_ttl_minus_one_repaired_on_429(self, redis_cache_env, identity_kind):
        """A key stuck at count >= 30 with TTL -1 must receive a TTL on the 429 path and unblock once expired."""
        cache = redis_cache_env
        request = _make_identity_request(identity_kind)
        key = Block404Middleware._cache_key(request)
        made_key = cache.make_and_validate_key(key)
        client = cache._cache.get_client(made_key, write=True)

        client.set(made_key, Block404Middleware.MAX_404_PER_MINUTE)
        assert client.ttl(made_key) == -1

        middleware = Block404Middleware(_make_get_response(200))
        blocked = middleware(request)
        assert blocked.status_code == 429
        assert blocked['Retry-After'] == Block404Middleware.RETRY_AFTER_SECONDS
        assert 0 < client.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

        # Simulate expiration and confirm subsequent API traffic is unblocked.
        client.delete(made_key)
        unblocked = middleware(_make_identity_request(identity_kind))
        assert unblocked.status_code == 200

    def test_stuck_ttl_minus_one_repaired_mid_window(self, redis_cache_env):
        """A mid-window key stuck with TTL -1 must gain a 60s TTL on the next API 404."""
        cache = redis_cache_env
        request = _make_identity_request('user')
        key = Block404Middleware._cache_key(request)
        made_key = cache.make_and_validate_key(key)
        client = cache._cache.get_client(made_key, write=True)

        client.set(made_key, 15)
        assert client.ttl(made_key) == -1

        middleware = Block404Middleware(_make_get_response(404))
        response = middleware(request)
        assert response.status_code == 404
        assert client.get(made_key) == b'16'
        assert 0 < client.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

    def test_ttl_not_extended_on_404_or_429(self, redis_cache_env):
        """Subsequent 404s and 429s must preserve the remaining window TTL instead of resetting to 60s."""
        cache = redis_cache_env
        request = _make_identity_request('user')
        key = Block404Middleware._cache_key(request)
        made_key = cache.make_and_validate_key(key)
        client = cache._cache.get_client(made_key, write=True)

        middleware_404 = Block404Middleware(_make_get_response(404))
        assert middleware_404(request).status_code == 404
        assert client.expire(made_key, 25)

        assert middleware_404(_make_identity_request('user')).status_code == 404
        assert client.get(made_key) == b'2'
        assert 0 < client.ttl(made_key) <= 25

        client.set(made_key, Block404Middleware.MAX_404_PER_MINUTE, ex=25)
        middleware_200 = Block404Middleware(_make_get_response(200))
        for _ in range(3):
            blocked = middleware_200(_make_identity_request('user'))
            assert blocked.status_code == 429
            assert 0 < client.ttl(made_key) <= 25

    def test_increment_uses_transactional_pipeline_without_exists(self, fakeredis_cache, monkeypatch):
        """_increment must use MULTI/EXEC INCR + EXPIRE NX without calling EXISTS."""
        recorded = {'pipeline_transactions': [], 'exists_calls': 0, 'commands': []}
        orig_pipeline = redis.Redis.pipeline
        orig_exists = redis.Redis.exists

        def spy_exists(self, *names):
            recorded['exists_calls'] += 1
            return orig_exists(self, *names)

        def spy_pipeline(self, transaction=True, shard_hint=None):
            recorded['pipeline_transactions'].append(transaction)
            pipe = orig_pipeline(self, transaction=transaction, shard_hint=shard_hint)
            orig_incr = pipe.incr
            orig_expire = pipe.expire

            def spy_incr(name, amount=1):
                recorded['commands'].append(('INCR', name, amount))
                return orig_incr(name, amount)

            def spy_expire(name, time, nx=False, xx=False, gt=False, lt=False):
                recorded['commands'].append(('EXPIRE', name, time, nx))
                return orig_expire(name, time, nx=nx, xx=xx, gt=gt, lt=lt)

            pipe.incr = spy_incr
            pipe.expire = spy_expire
            return pipe

        monkeypatch.setattr(redis.Redis, 'exists', spy_exists)
        monkeypatch.setattr(redis.Redis, 'pipeline', spy_pipeline)

        key = '404_counter:user:138'
        made_key = fakeredis_cache.make_and_validate_key(key)
        assert Block404Middleware._increment(fakeredis_cache, key) == 1
        assert recorded['exists_calls'] == 0
        assert recorded['pipeline_transactions'] == [True]
        assert recorded['commands'] == [
            ('INCR', made_key, 1),
            ('EXPIRE', made_key, Block404Middleware.WINDOW_SECONDS, True),
        ]

    def test_pipeline_response_error_fails_open_and_logs_warning(self, fakeredis_cache, monkeypatch, caplog):
        """An unexpected Pipeline.execute ResponseError must fail open without 500 and log a warning."""

        def failing_execute(self, raise_on_error=True):
            raise ResponseError('EXEC failed')

        monkeypatch.setattr(redis.client.Pipeline, 'execute', failing_execute)

        middleware = Block404Middleware(_make_get_response(404))
        with caplog.at_level(logging.WARNING, logger=block_404.__name__):
            response = middleware(_make_identity_request('user'))

        assert response.status_code == 404
        assert any(r.levelno == logging.WARNING and 'Failed to increment' in r.message for r in caplog.records)

    def test_corrupted_non_integer_value_deletes_key_and_recovers(self, fakeredis_cache, caplog):
        """A non-integer counter value fails open once, deletes the corrupt key, and recovers on the next 404."""
        request = _make_identity_request('user')
        key = Block404Middleware._cache_key(request)
        made_key = fakeredis_cache.make_and_validate_key(key)
        client = fakeredis_cache._cache.get_client(made_key, write=True)
        fakeredis_cache.set(key, 'not-an-int', timeout=60)

        middleware = Block404Middleware(_make_get_response(404))
        with caplog.at_level(logging.WARNING, logger=block_404.__name__):
            first = middleware(request)

        assert first.status_code == 404
        assert client.get(made_key) is None
        assert any(r.levelno == logging.WARNING for r in caplog.records)

        second = middleware(_make_identity_request('user'))
        assert second.status_code == 404
        assert client.get(made_key) == b'1'
        assert 0 < client.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

    def test_redis_below_7_logs_error_once_and_falls_back_including_429_repair(
        self, fakeredis_cache, monkeypatch, caplog
    ):
        """Redis < 7.0 logs one error, falls back to cache.add/incr, and repairs TTL -1 on 429."""
        monkeypatch.setattr(redis.Redis, 'info', lambda self, section=None: {'redis_version': '6.2.14'})

        middleware_404 = Block404Middleware(_make_get_response(404))
        with caplog.at_level(logging.ERROR, logger=block_404.__name__):
            for _ in range(Block404Middleware.MAX_404_PER_MINUTE + 1):
                middleware_404(_make_identity_request('user'))

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert 'Redis >= 7.0' in error_records[0].getMessage()
        assert block_404._redis_state.expire_nx_supported is False
        assert middleware_404(_make_identity_request('user')).status_code == 429

        # Stuck TTL: -1 key on Redis < 7.0 is still repaired via ttl() == -1 + expire().
        ip_request = _make_identity_request('ip')
        ip_key = Block404Middleware._cache_key(ip_request)
        made_ip_key = fakeredis_cache.make_and_validate_key(ip_key)
        client = fakeredis_cache._cache.get_client(made_ip_key, write=True)
        client.set(made_ip_key, Block404Middleware.MAX_404_PER_MINUTE)
        assert client.ttl(made_ip_key) == -1

        blocked = Block404Middleware(_make_get_response(200))(ip_request)
        assert blocked.status_code == 429
        assert 0 < client.ttl(made_ip_key) <= Block404Middleware.WINDOW_SECONDS

    def test_acl_blocked_info_with_redis_below_7_falls_back_on_first_nx_error(
        self, fakeredis_cache, monkeypatch, caplog
    ):
        """If INFO is blocked and EXPIRE NX raises wrong-arg ResponseError, switch once to fallback."""
        monkeypatch.setattr(
            redis.Redis,
            'info',
            lambda self, section=None: (_ for _ in ()).throw(ResponseError('NOPERM')),
        )
        orig_execute = redis.client.Pipeline.execute
        calls = {'count': 0}

        def fail_first_nx(self, raise_on_error=True):
            calls['count'] += 1
            if calls['count'] == 1:
                raise ResponseError("EXECABORT Transaction discarded: ERR wrong number of arguments for 'expire'")
            return orig_execute(self, raise_on_error=raise_on_error)

        monkeypatch.setattr(redis.client.Pipeline, 'execute', fail_first_nx)

        middleware = Block404Middleware(_make_get_response(404))
        with caplog.at_level(logging.ERROR, logger=block_404.__name__):
            resp1 = middleware(_make_identity_request('user'))
            resp2 = middleware(_make_identity_request('user'))

        assert resp1.status_code == 404
        assert resp2.status_code == 404
        assert calls['count'] == 1
        assert block_404._redis_state.expire_nx_supported is False
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1

        key = Block404Middleware._cache_key(_make_identity_request('user'))
        made_key = fakeredis_cache.make_and_validate_key(key)
        client = fakeredis_cache._cache.get_client(made_key, write=True)
        assert client.get(made_key) == b'2'
        assert 0 < client.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

    def test_missing_private_cache_attr_logs_warning_once_and_falls_back(self, caplog):
        """If Django alters RedisCache._cache/get_client, log once and fall back to cache.add/incr."""
        key_prefix = f'test-404-{uuid.uuid4().hex}'
        future_cfg = {
            'default': {
                'BACKEND': f'{_FutureDjangoRedisCache.__module__}.{_FutureDjangoRedisCache.__qualname__}',
                'LOCATION': 'redis://localhost:6379/0',
                'KEY_PREFIX': key_prefix,
                'OPTIONS': {
                    'connection_class': fakeredis.FakeRedisConnection,
                    'server': fakeredis.FakeServer(),
                },
            }
        }

        with override_settings(CACHES=future_cfg):
            middleware = Block404Middleware(_make_get_response(404))
            with caplog.at_level(logging.WARNING, logger=block_404.__name__):
                for _ in range(Block404Middleware.MAX_404_PER_MINUTE + 1):
                    middleware(_make_identity_request('user'))

            warnings = [r for r in caplog.records if r.levelno == logging.WARNING and '_cache.get_client' in r.message]
            assert len(warnings) == 1
            assert middleware(_make_identity_request('user')).status_code == 429
