"""
Tests for API throttling: Block404Middleware, PublicStreamThrottle,
PublicScheduleThrottle, and EventyayAnonRateThrottle / EventyayUserRateThrottle.

Uses LocMemCache isolation (override_settings) to ensure throttle state never
bleeds between tests and that the tests can run without a running Redis instance.
"""

import logging
import os
import uuid

import fakeredis
import pytest
from django.core.cache import caches
from django.core.cache.backends.redis import RedisCache as DjangoRedisCache
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django_redis import get_redis_connection
from redis.exceptions import ConnectionError as RedisConnectionError

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

@pytest.mark.django_db
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
# Block404Middleware Redis TTL tests
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
            },
            'redis': {
                'BACKEND': 'django_redis.cache.RedisCache',
                'LOCATION': redis_url,
                'KEY_PREFIX': key_prefix,
            },
        }

    server = fakeredis.FakeServer()
    location = f'redis://{key_prefix}:6379/0'
    return {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': location,
            'KEY_PREFIX': key_prefix,
            'OPTIONS': {
                'connection_class': fakeredis.FakeRedisConnection,
                'server': server,
            },
        },
        'redis': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': location,
            'KEY_PREFIX': key_prefix,
            'OPTIONS': {
                'CONNECTION_POOL_KWARGS': {
                    'connection_class': fakeredis.FakeRedisConnection,
                    'server': server,
                },
            },
        },
    }


def _make_identity_request(identity_kind: str):
    request = RequestFactory().get(f'{_API_PATH_PREFIX}v1/rooms/', REMOTE_ADDR='198.51.100.42')
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


@pytest.fixture(params=['fakeredis', 'live'])
def redis_cache_env(request):
    key_prefix = f'test-404-{uuid.uuid4().hex}'
    with override_settings(CACHES=_build_redis_cache_settings(request.param, key_prefix)):
        cache = caches[Block404Middleware.CACHE_ALIAS]
        try:
            yield cache
        finally:
            rc = get_redis_connection('redis')
            keys = list(rc.scan_iter(match=f'{key_prefix}:*'))
            if keys:
                rc.delete(*keys)


@pytest.fixture
def fakeredis_cache():
    key_prefix = f'test-404-{uuid.uuid4().hex}'
    with override_settings(CACHES=_build_redis_cache_settings('fakeredis', key_prefix)):
        yield caches[Block404Middleware.CACHE_ALIAS]


class TestBlock404MiddlewareRedis:
    def test_increment_initializes_counter_with_active_ttl(self, redis_cache_env):
        cache = redis_cache_env
        rc = get_redis_connection('redis')
        request = _make_identity_request('user')
        key = Block404Middleware._cache_key(request)
        made_key = cache.make_and_validate_key(key)

        assert Block404Middleware._increment(cache, key) == 1
        assert rc.get(made_key) == b'1'
        assert 0 < rc.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

        rc.delete(made_key)
        assert Block404Middleware(_make_get_response(404))(request).status_code == 404
        assert rc.get(made_key) == b'1'
        assert 0 < rc.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

    @pytest.mark.parametrize('identity_kind', ['user', 'token', 'ip'])
    def test_stuck_ttl_minus_one_repaired_on_429(self, redis_cache_env, identity_kind):
        cache = redis_cache_env
        rc = get_redis_connection('redis')
        request = _make_identity_request(identity_kind)
        made_key = cache.make_and_validate_key(Block404Middleware._cache_key(request))

        rc.set(made_key, Block404Middleware.MAX_404_PER_MINUTE)
        assert rc.ttl(made_key) == -1

        blocked = Block404Middleware(_make_get_response(200))(request)
        assert blocked.status_code == 429
        assert 0 < rc.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

        rc.delete(made_key)
        assert Block404Middleware(_make_get_response(200))(_make_identity_request(identity_kind)).status_code == 200

    def test_stuck_ttl_minus_one_repaired_mid_window(self, redis_cache_env):
        cache = redis_cache_env
        rc = get_redis_connection('redis')
        request = _make_identity_request('user')
        made_key = cache.make_and_validate_key(Block404Middleware._cache_key(request))

        rc.set(made_key, 15)
        assert rc.ttl(made_key) == -1

        assert Block404Middleware(_make_get_response(404))(request).status_code == 404
        assert rc.get(made_key) == b'16'
        assert 0 < rc.ttl(made_key) <= Block404Middleware.WINDOW_SECONDS

    def test_active_ttl_preserved_on_404_and_429(self, redis_cache_env):
        cache = redis_cache_env
        rc = get_redis_connection('redis')
        request = _make_identity_request('user')
        made_key = cache.make_and_validate_key(Block404Middleware._cache_key(request))

        mw_404 = Block404Middleware(_make_get_response(404))
        assert mw_404(request).status_code == 404
        rc.expire(made_key, 25)
        before_404 = rc.ttl(made_key)

        assert mw_404(_make_identity_request('user')).status_code == 404
        assert rc.get(made_key) == b'2'
        assert before_404 - 2 <= rc.ttl(made_key) <= before_404

        rc.set(made_key, Block404Middleware.MAX_404_PER_MINUTE, ex=25)
        mw_200 = Block404Middleware(_make_get_response(200))
        for _ in range(3):
            before_429 = rc.ttl(made_key)
            assert mw_200(_make_identity_request('user')).status_code == 429
            assert before_429 - 2 <= rc.ttl(made_key) <= before_429

    def test_redis_errors_fail_open_without_leaking_ip(self, fakeredis_cache, monkeypatch, caplog):
        def _warnings():
            return [r.getMessage() for r in caplog.records if r.name == block_404.__name__]

        with caplog.at_level(logging.WARNING, logger=block_404.__name__):
            caplog.clear()
            with monkeypatch.context() as mp:
                mp.setattr(
                    DjangoRedisCache,
                    'get',
                    lambda self, key, default=None, version=None: (_ for _ in ()).throw(RedisConnectionError('down')),
                )
                assert Block404Middleware(_make_get_response(200))(_make_identity_request('ip')).status_code == 200
            assert _warnings() == ['Failed to read 404 counter: ConnectionError']

            caplog.clear()
            with monkeypatch.context() as mp:
                mp.setattr(
                    DjangoRedisCache,
                    'add',
                    lambda self, key, value, timeout=None, version=None: False,
                )
                mp.setattr(
                    DjangoRedisCache,
                    'incr',
                    lambda self, key, delta=1, version=None: (_ for _ in ()).throw(RedisConnectionError('down')),
                )
                assert Block404Middleware(_make_get_response(404))(_make_identity_request('ip')).status_code == 404
            assert _warnings() == ['Failed to increment 404 counter: ConnectionError']

            rc = get_redis_connection('redis')
            ip_req = _make_identity_request('ip')
            made_ip = fakeredis_cache.make_and_validate_key(Block404Middleware._cache_key(ip_req))
            rc.set(made_ip, Block404Middleware.MAX_404_PER_MINUTE)
            caplog.clear()
            with monkeypatch.context() as mp:
                mp.setattr(
                    block_404,
                    'get_redis_connection',
                    lambda alias='redis': (_ for _ in ()).throw(RedisConnectionError('down')),
                )
                assert Block404Middleware(_make_get_response(200))(ip_req).status_code == 429
            assert _warnings() == ['Failed to ensure TTL on 404 counter: ConnectionError']
