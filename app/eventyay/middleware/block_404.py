import logging
from dataclasses import dataclass

from django.core.cache import caches
from django.core.cache.backends.base import BaseCache
from django.core.cache.backends.redis import RedisCache as DjangoRedisCache
from django.http import HttpRequest, HttpResponse
from redis import Redis
from redis.exceptions import RedisError, ResponseError

from eventyay.helpers.http import get_client_ip

logger = logging.getLogger(__name__)

# Only guard API paths — HTML pages, static files, and admin URLs are excluded
# to avoid blocking legitimate browsers under shared NAT or misconfigured proxies.
_API_PATH_PREFIX = '/api/'
_CACHE_ERRORS = (RedisError, OSError)


@dataclass
class _RedisState:
    # Cached per process after the first Redis version check or EXPIRE NX rejection.
    expire_nx_supported: bool | None = None
    missing_client_warned: bool = False


_redis_state = _RedisState()


def is_expire_nx_unsupported_error(exc: ResponseError) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in ('execabort', 'wrong number of arguments', 'syntax', 'nx'))


def mark_expire_nx_unsupported(reason: object) -> None:
    if _redis_state.expire_nx_supported is not False:
        logger.error(
            'Block404Middleware requires Redis >= 7.0 for atomic EXPIRE NX (%s); falling back to cache.add/incr.',
            reason,
        )
        _redis_state.expire_nx_supported = False


def get_redis_client(cache: BaseCache, made_key: str) -> Redis | None:
    if not isinstance(cache, DjangoRedisCache):
        return None
    try:
        return cache._cache.get_client(made_key, write=True)
    except AttributeError:
        if not _redis_state.missing_client_warned:
            logger.warning('Django RedisCache does not expose _cache.get_client(); falling back to cache.add/incr.')
            _redis_state.missing_client_warned = True
        return None


def supports_expire_nx(client: Redis) -> bool:
    if _redis_state.expire_nx_supported is not None:
        return _redis_state.expire_nx_supported
    try:
        server_info = client.info('server')
    except ResponseError:
        # INFO may be restricted by ACLs or unimplemented in fake backends;
        # assume Redis >= 7.0 unless EXPIRE ... NX fails at execution time.
        _redis_state.expire_nx_supported = True
        return True

    raw_version = server_info.get('redis_version') if isinstance(server_info, dict) else None
    try:
        major_version = int(str(raw_version).split('.', 1)[0])
    except (ValueError, TypeError):
        mark_expire_nx_unsupported(f'unrecognized redis_version={raw_version!r}')
        return False

    if major_version < 7:
        mark_expire_nx_unsupported(f'detected redis_version={raw_version}')
        return False

    _redis_state.expire_nx_supported = True
    return True


def cache_incr_with_ttl(cache: BaseCache, key: str, timeout: int) -> int:
    for _ in range(3):
        if cache.add(key, 1, timeout=timeout):
            return 1
        try:
            return cache.incr(key)
        except ValueError:
            continue
    cache.set(key, 1, timeout=timeout)
    return 1


def ensure_counter_ttl(cache: BaseCache, key: str, timeout: int) -> None:
    made_key = cache.make_and_validate_key(key)
    client = get_redis_client(cache, made_key)
    if client is None:
        return

    if supports_expire_nx(client):
        try:
            client.expire(made_key, timeout, nx=True)
            return
        except ResponseError as exc:
            if not is_expire_nx_unsupported_error(exc):
                raise
            mark_expire_nx_unsupported(exc)

    if client.ttl(made_key) == -1:
        client.expire(made_key, timeout)


class Block404Middleware:
    """
    Middleware that tracks the number of 404 responses *on API paths* per client
    IP (or user id for authenticated requests) and returns 429 Too Many Requests
    once the limit is breached.

    Scoped to ``/api/`` paths only so that normal browser navigation, static-file
    misses, and CMS 404s never trigger the block.

    Requires Redis >= 7.0 on the ``default`` cache for atomic ``EXPIRE ... NX``
    TTL enforcement; older Redis versions fall back to ``cache.add``/``cache.incr``
    with non-atomic ``TTL == -1`` repair on 429 responses.
    """

    MAX_404_PER_MINUTE = 30
    WINDOW_SECONDS = 60
    CACHE_ALIAS = 'default'
    RETRY_AFTER_SECONDS = '60'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Only guard API paths
        if not request.path.startswith(_API_PATH_PREFIX):
            return self.get_response(request)

        key = self._cache_key(request)
        cache = caches[self.CACHE_ALIAS]

        try:
            count = int(cache.get(key) or 0)
        except (ValueError, TypeError):
            count = 0

        if count >= self.MAX_404_PER_MINUTE:
            try:
                ensure_counter_ttl(cache, key, self.WINDOW_SECONDS)
            except _CACHE_ERRORS as exc:
                logger.warning('Failed to ensure TTL on 404 counter for key %s: %s', key, exc)
            return self._too_many_requests_response()

        response = self.get_response(request)

        if response.status_code != 404:
            return response

        try:
            count = self._increment(cache, key)
        except _CACHE_ERRORS as exc:
            logger.warning('Failed to increment 404 counter for key %s: %s', key, exc)
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
    def _increment(cls, cache: BaseCache, key: str) -> int:
        made_key = cache.make_and_validate_key(key)
        client = get_redis_client(cache, made_key)
        if client is not None and supports_expire_nx(client):
            pipe = client.pipeline(transaction=True)
            pipe.incr(made_key)
            pipe.expire(made_key, cls.WINDOW_SECONDS, nx=True)
            try:
                count, _ = pipe.execute()
                return int(count)
            except ResponseError as exc:
                if is_expire_nx_unsupported_error(exc):
                    mark_expire_nx_unsupported(exc)
                else:
                    if 'not an integer' in str(exc).lower():
                        client.delete(made_key)
                    raise
        return cache_incr_with_ttl(cache, key, cls.WINDOW_SECONDS)

    @classmethod
    def _too_many_requests_response(cls):
        return HttpResponse(
            content='Too many 404 responses – request throttled.',
            status=429,
            headers={'Retry-After': cls.RETRY_AFTER_SECONDS},
        )
