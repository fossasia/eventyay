import logging
import pickle
from dataclasses import dataclass

from django.core.cache import caches
from django.core.cache.backends.base import BaseCache
from django.core.cache.backends.redis import RedisCache as DjangoRedisCache
from django.http import HttpRequest, HttpResponse
from redis import Redis
from redis.exceptions import NoPermissionError, RedisError, ResponseError

from eventyay.helpers.http import get_client_ip


logger = logging.getLogger(__name__)

# Only guard API paths — HTML pages, static files, and admin URLs are excluded
# to avoid blocking legitimate browsers under shared NAT or misconfigured proxies.
_API_PATH_PREFIX = '/api/'
_CACHE_ERRORS = (RedisError, OSError)


@dataclass
class _RedisState:
    # Cached per process after the first Redis capability or ACL check.
    expire_nx_supported: bool | None = None
    expire_acl_denied: bool = False
    missing_client_warned: bool = False


_redis_state = _RedisState()


def _error_detail(exc: ResponseError) -> str:
    msg = str(exc).lower()
    if 'caused error:' in msg:
        return msg.split('caused error:', 1)[1].strip()
    return msg


def is_expire_acl_denied_error(exc: ResponseError, *, from_pipeline: bool = False) -> bool:
    msg = str(exc).lower()
    if not (isinstance(exc, NoPermissionError) or 'noperm' in msg or 'no permissions' in msg):
        return False
    if not from_pipeline:
        return True
    return "'expire'" in msg or '(expire ' in msg


def is_expire_nx_unsupported_error(exc: ResponseError, *, from_pipeline: bool = False) -> bool:
    if is_expire_acl_denied_error(exc, from_pipeline=from_pipeline):
        return False
    detail = _error_detail(exc)
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


def mark_expire_nx_unsupported(reason: object) -> None:
    if _redis_state.expire_nx_supported is not False:
        logger.error(
            'Block404Middleware requires Redis >= 7.0 for atomic EXPIRE NX (%s); falling back to cache.add/incr.',
            reason,
        )
        _redis_state.expire_nx_supported = False


def mark_expire_acl_denied(reason: object) -> None:
    if not _redis_state.expire_acl_denied:
        logger.error(
            'Redis ACL denies EXPIRE for Block404Middleware (%s); falling back to SET EX / cache.add/incr.',
            reason,
        )
        _redis_state.expire_acl_denied = True


def _handle_expire_fallback(exc: ResponseError, *, from_pipeline: bool = False) -> bool:
    if is_expire_acl_denied_error(exc, from_pipeline=from_pipeline):
        mark_expire_acl_denied(exc)
        return True
    if is_expire_nx_unsupported_error(exc, from_pipeline=from_pipeline):
        mark_expire_nx_unsupported(exc)
        return True
    return False


def _reset_if_non_integer(client: Redis, made_key: str, exc: Exception, attempt: int) -> bool:
    if attempt == 0 and isinstance(exc, ResponseError) and 'not an integer' in str(exc).lower():
        logger.warning('Resetting corrupted 404 counter for Redis key %s.', made_key)
        client.delete(made_key)
        return True
    return False


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


def _set_ttl_without_expire(client: Redis, made_key: str, timeout: int) -> None:
    if client.ttl(made_key) != -1:
        return
    current = client.get(made_key)
    if current is None:
        return
    try:
        counter_value = int(current)
    except (ValueError, TypeError):
        client.delete(made_key)
        return
    client.set(made_key, counter_value, ex=timeout, xx=True)


def _repair_ttl_without_nx(client: Redis, made_key: str, timeout: int) -> None:
    if _redis_state.expire_acl_denied:
        _set_ttl_without_expire(client, made_key, timeout)
        return
    if client.ttl(made_key) == -1:
        try:
            client.expire(made_key, timeout)
        except ResponseError as exc:
            if not is_expire_acl_denied_error(exc):
                raise
            mark_expire_acl_denied(exc)
            _set_ttl_without_expire(client, made_key, timeout)


def cache_incr_with_ttl(
    cache: BaseCache,
    key: str,
    timeout: int,
    *,
    use_ttl_guard: bool = False,
) -> int:
    guard_key = f'{key}:ttl_guard'
    for _ in range(3):
        if cache.add(key, 1, timeout=timeout):
            if use_ttl_guard:
                cache.set(guard_key, 1, timeout=timeout)
            return 1
        try:
            count = int(cache.incr(key))
            if use_ttl_guard and cache.add(guard_key, 1, timeout=timeout):
                cache.touch(key, timeout=timeout)
            return count
        except ValueError:
            continue
        except (ResponseError, TypeError) as exc:
            if isinstance(exc, ResponseError) and 'not an integer' not in str(exc).lower():
                raise
            logger.warning('Resetting malformed 404 counter for key %s.', key)
            cache.delete(key)
            continue
    cache.set(key, 1, timeout=timeout)
    if use_ttl_guard:
        cache.set(guard_key, 1, timeout=timeout)
    return 1


def ensure_counter_ttl(cache: BaseCache, key: str, timeout: int) -> None:
    made_key = cache.make_and_validate_key(key)
    client = get_redis_client(cache, made_key)
    if client is None:
        # Public BaseCache exposes no ttl() check; a companion guard key lets us
        # attach a single fixed-window TTL without extending active counters on polls.
        if cache.add(f'{key}:ttl_guard', 1, timeout=timeout):
            cache.touch(key, timeout=timeout)
        return

    if not _redis_state.expire_acl_denied and supports_expire_nx(client):
        try:
            client.expire(made_key, timeout, nx=True)
            return
        except ResponseError as exc:
            if not _handle_expire_fallback(exc):
                raise

    _repair_ttl_without_nx(client, made_key, timeout)


class Block404Middleware:
    """
    Middleware that tracks the number of 404 responses *on API paths* per client
    IP (or user id for authenticated requests) and returns 429 Too Many Requests
    once the limit is breached.

    Scoped to ``/api/`` paths only so that normal browser navigation, static-file
    misses, and CMS 404s never trigger the block.

    Requires Redis >= 7.0 on the ``default`` cache for atomic ``EXPIRE ... NX``
    TTL enforcement; older Redis versions or ACL-restricted ``EXPIRE`` environments
    fall back to ``cache.add``/``cache.incr`` with non-atomic ``TTL == -1`` repair.
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
        except _CACHE_ERRORS as exc:
            logger.warning('Failed to read 404 counter for key %s: %s', key, exc)
            return self.get_response(request)
        except (ValueError, TypeError, pickle.UnpicklingError, EOFError):
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
    def _increment_with_pipeline(cls, client: Redis, made_key: str) -> int | None:
        """
        Execute INCR + EXPIRE ... NX inside MULTI/EXEC.

        Returns the committed integer count, or ``None`` if Redis aborted the
        transaction cleanly before INCR (e.g. EXECABORT on Redis < 7 or -expire ACL)
        so callers can fall back to ``cache_incr_with_ttl`` without double counting.
        """
        for attempt in range(2):
            pipe = client.pipeline(transaction=True)
            pipe.incr(made_key)
            pipe.expire(made_key, cls.WINDOW_SECONDS, nx=True)
            try:
                results = pipe.execute(raise_on_error=False)
            except ResponseError as exc:
                if _handle_expire_fallback(exc, from_pipeline=True):
                    return None
                if _reset_if_non_integer(client, made_key, exc, attempt):
                    continue
                raise

            count_result, expire_result = results
            if isinstance(count_result, Exception):
                if _reset_if_non_integer(client, made_key, count_result, attempt):
                    continue
                raise count_result

            count = int(count_result)
            if isinstance(expire_result, Exception):
                # INCR already committed on Redis; never fall through to
                # cache_incr_with_ttl or the request would be counted twice.
                if not isinstance(expire_result, ResponseError) or not _handle_expire_fallback(
                    expire_result, from_pipeline=True
                ):
                    raise expire_result
                _repair_ttl_without_nx(client, made_key, cls.WINDOW_SECONDS)
            return count

        return None

    @classmethod
    def _increment(cls, cache: BaseCache, key: str) -> int:
        made_key = cache.make_and_validate_key(key)
        client = get_redis_client(cache, made_key)
        if client is not None and not _redis_state.expire_acl_denied and supports_expire_nx(client):
            count = cls._increment_with_pipeline(client, made_key)
            if count is not None:
                return count

        count = cache_incr_with_ttl(
            cache,
            key,
            cls.WINDOW_SECONDS,
            use_ttl_guard=(client is None),
        )
        if client is not None and count > 1:
            _repair_ttl_without_nx(client, made_key, cls.WINDOW_SECONDS)
        return count

    @classmethod
    def _too_many_requests_response(cls):
        return HttpResponse(
            content='Too many 404 responses – request throttled.',
            status=429,
            headers={'Retry-After': cls.RETRY_AFTER_SECONDS},
        )
