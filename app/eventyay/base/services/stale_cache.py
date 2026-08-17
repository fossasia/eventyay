import hashlib
import logging

from django.core.cache import cache
from django.db import DatabaseError, OperationalError

logger = logging.getLogger(__name__)

NONE_SENTINEL = 'none'
_CACHE_ERRORS = (ConnectionError, TimeoutError, OSError)
_DB_ERRORS = (DatabaseError, OperationalError)

CATALOG_HOT_TTL = 300
CATALOG_STALE_TTL = 3600
SCHEDULE_HOT_TTL = 300
SCHEDULE_STALE_TTL = 3600

CATALOG_NAMES = ('tracks', 'tags', 'submission-types', 'rooms')


def cache_get(key):
    try:
        return cache.get(key)
    except _CACHE_ERRORS as exc:
        logger.warning('Cache read failed for %s: %s', key, exc)
        return None


def cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except _CACHE_ERRORS as exc:
        logger.warning('Cache write failed for %s: %s', key, exc)


def cache_delete(*keys):
    for key in keys:
        try:
            cache.delete(key)
        except _CACHE_ERRORS as exc:
            logger.warning('Cache delete failed for %s: %s', key, exc)


def store_hot_and_stale(hot_key, stale_key, value, hot_ttl, stale_ttl):
    cache_set(hot_key, value, hot_ttl)
    cache_set(stale_key, value, stale_ttl)


def deserialize_none_sentinel(cached):
    return None if cached == NONE_SENTINEL else cached


def get_stale_cached(hot_key, stale_key, loader, hot_ttl, stale_ttl, *, log_context=''):
    cached = cache_get(hot_key)
    if cached is not None:
        return deserialize_none_sentinel(cached)

    try:
        value = loader()
    except _DB_ERRORS as exc:
        stale = cache_get(stale_key)
        if stale is not None:
            logger.warning('Serving stale cache for %s after DB error: %s', log_context or hot_key, exc)
            return deserialize_none_sentinel(stale)
        raise

    store_hot_and_stale(hot_key, stale_key, value if value is not None else NONE_SENTINEL, hot_ttl, stale_ttl)
    return value


def schedule_cache_version_key(event_id):
    return f'api:schedule:ver:{event_id}'


def get_schedule_cache_version(event_id):
    return cache_get(schedule_cache_version_key(event_id)) or 0


def bump_schedule_cache_version(event_id):
    key = schedule_cache_version_key(event_id)
    try:
        cache.incr(key)
    except ValueError:
        cache_set(key, 1, None)


def catalog_cache_keys(event_id, catalog):
    prefix = f'api:catalog:{event_id}:{catalog}'
    return f'{prefix}:hot', f'{prefix}:stale'


def schedule_detail_cache_keys(event_id, schedule_id, expand_key, user_scope):
    version = get_schedule_cache_version(event_id)
    prefix = f'api:schedule:{event_id}:v{version}:{schedule_id}:{user_scope}:{expand_key}'
    return f'{prefix}:hot', f'{prefix}:stale'


def talk_slots_list_cache_keys(event_id, user_scope, expand_key, filter_key):
    version = get_schedule_cache_version(event_id)
    prefix = f'api:talk-slots:{event_id}:v{version}:{user_scope}:{expand_key}:{filter_key}'
    return f'{prefix}:hot', f'{prefix}:stale'


def next_stream_cache_keys(room_id):
    prefix = f'stream:next:{room_id}'
    return prefix, f'{prefix}:stale'


def invalidate_event_catalog_cache(event_id):
    for catalog in CATALOG_NAMES:
        invalidate_catalog_cache(event_id, catalog)


def invalidate_catalog_cache(event_id, catalog):
    hot, stale = catalog_cache_keys(event_id, catalog)
    cache_delete(hot, stale)


def invalidate_next_stream_cache(room_id):
    hot, stale = next_stream_cache_keys(room_id)
    cache_delete(hot, stale)


def get_cached_catalog_list(event_id, catalog, loader):
    hot_key, stale_key = catalog_cache_keys(event_id, catalog)
    cached = get_stale_cached(
        hot_key,
        stale_key,
        loader,
        CATALOG_HOT_TTL,
        CATALOG_STALE_TTL,
        log_context=f'catalog {catalog} event {event_id}',
    )
    return deserialize_none_sentinel(cached)


def get_cached_schedule_detail(event_id, schedule_id, expand_key, user_scope, loader):
    hot_key, stale_key = schedule_detail_cache_keys(event_id, schedule_id, expand_key, user_scope)
    cached = get_stale_cached(
        hot_key,
        stale_key,
        loader,
        SCHEDULE_HOT_TTL,
        SCHEDULE_STALE_TTL,
        log_context=f'schedule {schedule_id} event {event_id}',
    )
    return deserialize_none_sentinel(cached)


def get_cached_talk_slots_list(event_id, user_scope, expand_key, filter_key, loader):
    hot_key, stale_key = talk_slots_list_cache_keys(event_id, user_scope, expand_key, filter_key)
    cached = get_stale_cached(
        hot_key,
        stale_key,
        loader,
        SCHEDULE_HOT_TTL,
        SCHEDULE_STALE_TTL,
        log_context=f'talk slots event {event_id}',
    )
    return deserialize_none_sentinel(cached)


def talk_slots_filter_key(request, filter_fields):
    parts = []
    for field in sorted(filter_fields):
        value = request.query_params.get(field)
        if value is not None:
            parts.append(f'{field}={value}')
    search = request.query_params.get('search')
    if search:
        parts.append(f'search={search}')
    if not parts:
        return 'default'
    return hashlib.md5('|'.join(parts).encode(), usedforsecurity=False).hexdigest()
