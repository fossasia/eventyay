import logging
import pickle

from django.core.cache import caches
from django.core.cache.backends.redis import RedisCache as DjangoRedisCache
from django.http import HttpResponse
from redis.exceptions import NoPermissionError, RedisError, ResponseError

from eventyay.helpers.http import get_client_ip


logger = logging.getLogger(__name__)

# Only guard API paths — HTML pages, static files, and admin URLs are excluded
# to avoid blocking legitimate browsers under shared NAT or misconfigured proxies.
_API_PATH_PREFIX = '/api/'
_CACHE_ERRORS = (RedisError, OSError)


def _get_redis_client(cache, made_key):
    if not isinstance(cache, DjangoRedisCache):
        return None
    try:
        return cache._cache.get_client(made_key, write=True)
    except AttributeError:
        return None


def _is_expire_nx_unsupported(exc):
    if isinstance(exc, NoPermissionError):
        return False
    msg = str(exc).lower()
    detail = msg.split('caused error:', 1)[1].strip() if 'caused error:' in msg else msg
    if 'noperm' in detail or 'no permissions' in detail:
        return False
    return any(
        token in detail
        for token in (
            'wrong number of arguments',
            'syntax error',
            'unknown option',
            'unsupported',
            'not supported',
        )
    )


class Block404Middleware:
    """
    Middleware that tracks the number of 404 responses *on API paths* per client
    IP (or user id for authenticated requests) and returns 429 Too Many Requests
    once the limit is breached.

    Scoped to ``/api/`` paths only so that normal browser navigation, static-file
    misses, and CMS 404s never trigger the block.
    """

    MAX_404_PER_MINUTE = 30
    WINDOW_SECONDS = 60
    CACHE_ALIAS = 'default'
    RETRY_AFTER_SECONDS = '60'
    _expire_nx_supported = True

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only guard API paths
        if not request.path.startswith(_API_PATH_PREFIX):
            return self.get_response(request)

        key = self._cache_key(request)
        cache = caches[self.CACHE_ALIAS]

        try:
            count = int(cache.get(key) or 0)
        except _CACHE_ERRORS as exc:
            logger.warning('Failed to read 404 counter: %s', type(exc).__name__)
            return self.get_response(request)
        except (ValueError, TypeError, pickle.UnpicklingError, EOFError):
            count = 0

        if count >= self.MAX_404_PER_MINUTE:
            try:
                self._ensure_ttl(cache, key)
            except _CACHE_ERRORS as exc:
                logger.warning('Failed to ensure TTL on 404 counter: %s', type(exc).__name__)
            return self._too_many_requests_response()

        response = self.get_response(request)

        if response.status_code != 404:
            return response

        try:
            count = self._increment(cache, key)
        except _CACHE_ERRORS as exc:
            logger.warning('Failed to increment 404 counter: %s', type(exc).__name__)
            return response

        if count > self.MAX_404_PER_MINUTE:
            return self._too_many_requests_response()
        return response

    @staticmethod
    def _cache_key(request):
        """
        Key authenticated requests by user / token identity so a single bad
        client behind shared NAT does not block other users at the same IP.
        """
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            return f'404_counter:user:{user.pk}'
        auth = getattr(request, 'auth', None)
        if auth is not None:
            return f'404_counter:token:{type(auth).__name__}_{auth.pk}'
        ip = get_client_ip(request)
        return f'404_counter:ip:{ip}'

    @classmethod
    def _disable_expire_nx(cls, exc):
        if cls._expire_nx_supported:
            cls._expire_nx_supported = False
            logger.warning('Redis EXPIRE NX unsupported (%s); falling back to cache.add/incr.', type(exc).__name__)

    @classmethod
    def _ensure_ttl(cls, cache, key):
        made_key = cache.make_and_validate_key(key)
        client = _get_redis_client(cache, made_key)
        if client is None:
            return
        if cls._expire_nx_supported:
            try:
                client.expire(made_key, cls.WINDOW_SECONDS, nx=True)
                return
            except ResponseError as exc:
                if not _is_expire_nx_unsupported(exc):
                    raise
                cls._disable_expire_nx(exc)
        if client.ttl(made_key) == -1:
            client.expire(made_key, cls.WINDOW_SECONDS)

    @classmethod
    def _increment(cls, cache, key):
        made_key = cache.make_and_validate_key(key)
        client = _get_redis_client(cache, made_key)
        if client is not None and cls._expire_nx_supported:
            pipe = client.pipeline(transaction=True)
            pipe.incr(made_key)
            pipe.expire(made_key, cls.WINDOW_SECONDS, nx=True)
            try:
                count_result, expire_result = pipe.execute(raise_on_error=False)
                if isinstance(count_result, Exception):
                    if isinstance(count_result, ResponseError) and 'not an integer' in str(count_result).lower():
                        client.delete(made_key)
                        return cls._fallback_incr(cache, key, client, made_key)
                    raise count_result
                count = int(count_result)
                if isinstance(expire_result, Exception):
                    if not isinstance(expire_result, ResponseError) or not _is_expire_nx_unsupported(expire_result):
                        raise expire_result
                    cls._disable_expire_nx(expire_result)
                    if client.ttl(made_key) == -1:
                        client.expire(made_key, cls.WINDOW_SECONDS)
                return count
            except ResponseError as exc:
                if _is_expire_nx_unsupported(exc):
                    cls._disable_expire_nx(exc)
                elif 'not an integer' in str(exc).lower():
                    client.delete(made_key)
                else:
                    raise

        return cls._fallback_incr(cache, key, client, made_key)

    @classmethod
    def _fallback_incr(cls, cache, key, client, made_key):
        for _ in range(3):
            if cache.add(key, 1, timeout=cls.WINDOW_SECONDS):
                return 1
            try:
                count = int(cache.incr(key))
                if client is not None and client.ttl(made_key) == -1:
                    client.expire(made_key, cls.WINDOW_SECONDS)
                return count
            except ValueError:
                continue
            except (ResponseError, TypeError) as exc:
                if isinstance(exc, ResponseError) and 'not an integer' not in str(exc).lower():
                    raise
                cache.delete(key)
        cache.set(key, 1, timeout=cls.WINDOW_SECONDS)
        return 1

    @classmethod
    def _too_many_requests_response(cls):
        return HttpResponse(
            content='Too many 404 responses – request throttled.',
            status=429,
            headers={'Retry-After': cls.RETRY_AFTER_SECONDS},
        )
