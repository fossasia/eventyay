import hashlib
import json
import logging
import threading

from django.core.cache import cache
from django.db import DatabaseError, OperationalError, transaction

logger = logging.getLogger(__name__)

NONE_SENTINEL = 'none'
_CACHE_ERRORS = (ConnectionError, TimeoutError, OSError)
_DB_ERRORS = (DatabaseError, OperationalError)

CATALOG_HOT_TTL = 300
CATALOG_STALE_TTL = 3600
SCHEDULE_HOT_TTL = 300
SCHEDULE_STALE_TTL = 3600

CATALOG_NAMES = ('tracks', 'tags', 'submission-types')


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


def api_cache_fingerprint(data):
    return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode(), usedforsecurity=False).hexdigest()


def wrap_api_cache_payload(data):
    return {'payload': data, 'etag': api_cache_fingerprint(data)}


def unwrap_api_cache_payload(cached):
    if isinstance(cached, dict) and 'payload' in cached and 'etag' in cached:
        return cached['payload'], cached['etag']
    return cached, None


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


_bump_on_commit_local = threading.local()


def bump_schedule_cache_version_on_commit(event_id):
    """Bump at most once per event per database transaction."""
    pending = getattr(_bump_on_commit_local, 'pending', None)
    if pending is None:
        pending = set()
        _bump_on_commit_local.pending = pending
    if event_id in pending:
        return
    pending.add(event_id)
    transaction.on_commit(lambda: _flush_schedule_cache_bump(event_id))


def _flush_schedule_cache_bump(event_id):
    pending = getattr(_bump_on_commit_local, 'pending', None)
    if pending is not None:
        pending.discard(event_id)
    bump_schedule_cache_version(event_id)


def api_locale_key(request, event):
    """Cache key segment for ?lang= responses (DocumentedI18nField override)."""
    if not event:
        return 'all'
    params = getattr(request, 'query_params', request.GET)
    locale = params.get('lang')
    if locale and locale in event.locales:
        return locale
    return 'all'


def catalog_cache_version_key(event_id, catalog):
    return f'api:catalog:ver:{event_id}:{catalog}'


def get_catalog_cache_version(event_id, catalog):
    return cache_get(catalog_cache_version_key(event_id, catalog)) or 0


def bump_catalog_cache_version(event_id, catalog):
    key = catalog_cache_version_key(event_id, catalog)
    try:
        cache.incr(key)
    except ValueError:
        cache_set(key, 1, None)


def catalog_cache_keys(event_id, catalog, locale_key='all'):
    version = get_catalog_cache_version(event_id, catalog)
    prefix = f'api:catalog:{event_id}:{catalog}:v{version}:{locale_key}'
    return f'{prefix}:hot', f'{prefix}:stale'


def schedule_detail_cache_keys(event_id, schedule_id, expand_key, user_scope, locale_key='all'):
    version = get_schedule_cache_version(event_id)
    prefix = f'api:schedule:{event_id}:v{version}:{schedule_id}:{user_scope}:{locale_key}:{expand_key}'
    return f'{prefix}:hot', f'{prefix}:stale'


def talk_slots_list_cache_keys(event_id, user_scope, expand_key, filter_key, locale_key='all'):
    version = get_schedule_cache_version(event_id)
    prefix = f'api:talk-slots:{event_id}:v{version}:{user_scope}:{locale_key}:{expand_key}:{filter_key}'
    return f'{prefix}:hot', f'{prefix}:stale'


def next_stream_cache_keys(room_id):
    prefix = f'stream:next:{room_id}'
    return prefix, f'{prefix}:stale'


def invalidate_event_catalog_cache(event_id):
    for catalog in CATALOG_NAMES:
        invalidate_catalog_cache(event_id, catalog)


def invalidate_catalog_cache(event_id, catalog):
    bump_catalog_cache_version(event_id, catalog)


def invalidate_next_stream_cache(room_id):
    hot, stale = next_stream_cache_keys(room_id)
    cache_delete(hot, stale)


def get_cached_catalog_list(event_id, catalog, locale_key, loader):
    hot_key, stale_key = catalog_cache_keys(event_id, catalog, locale_key)

    def wrapping_loader():
        return wrap_api_cache_payload(loader())

    cached = get_stale_cached(
        hot_key,
        stale_key,
        wrapping_loader,
        CATALOG_HOT_TTL,
        CATALOG_STALE_TTL,
        log_context=f'catalog {catalog} event {event_id}',
    )
    data, etag = unwrap_api_cache_payload(deserialize_none_sentinel(cached))
    return data, etag


def get_cached_schedule_detail(event_id, schedule_id, expand_key, user_scope, locale_key, loader):
    hot_key, stale_key = schedule_detail_cache_keys(
        event_id, schedule_id, expand_key, user_scope, locale_key
    )

    def wrapping_loader():
        return wrap_api_cache_payload(loader())

    cached = get_stale_cached(
        hot_key,
        stale_key,
        wrapping_loader,
        SCHEDULE_HOT_TTL,
        SCHEDULE_STALE_TTL,
        log_context=f'schedule {schedule_id} event {event_id}',
    )
    data, etag = unwrap_api_cache_payload(deserialize_none_sentinel(cached))
    return data, etag


def video_spa_schedule_cache_keys(event_id, schedule_id, featured_key):
    version = get_schedule_cache_version(event_id)
    prefix = f'api:video-spa:{event_id}:v{version}:{schedule_id}:{featured_key}'
    return f'{prefix}:hot', f'{prefix}:stale'


def get_cached_video_spa_schedule(event_id, schedule_id, featured_key, loader):
    hot_key, stale_key = video_spa_schedule_cache_keys(event_id, schedule_id, featured_key)
    return get_stale_cached(
        hot_key,
        stale_key,
        loader,
        SCHEDULE_HOT_TTL,
        SCHEDULE_STALE_TTL,
        log_context=f'video spa schedule {schedule_id} event {event_id}',
    )


def get_cached_talk_slots_list(event_id, user_scope, expand_key, filter_key, locale_key, loader):
    hot_key, stale_key = talk_slots_list_cache_keys(
        event_id, user_scope, expand_key, filter_key, locale_key
    )

    def wrapping_loader():
        return wrap_api_cache_payload(loader())

    cached = get_stale_cached(
        hot_key,
        stale_key,
        wrapping_loader,
        SCHEDULE_HOT_TTL,
        SCHEDULE_STALE_TTL,
        log_context=f'talk slots event {event_id}',
    )
    data, etag = unwrap_api_cache_payload(deserialize_none_sentinel(cached))
    return data, etag


def talk_slots_filter_key(request, filter_fields):
    params = getattr(request, 'query_params', request.GET)
    parts = []
    for field in sorted(filter_fields):
        value = params.get(field)
        if value is not None:
            parts.append(f'{field}={value}')
    search = params.get('search')
    if search:
        parts.append(f'search={search}')
    ordering = params.get('ordering')
    if ordering:
        parts.append(f'ordering={ordering}')
    for key in ('page', 'page_size', 'limit', 'offset'):
        value = params.get(key)
        if value is not None:
            parts.append(f'{key}={value}')
    if not any(params.get(key) is not None for key in ('page', 'page_size', 'limit', 'offset')):
        parts.append('page=1')
    if not parts:
        return 'default'
    return hashlib.md5('|'.join(parts).encode(), usedforsecurity=False).hexdigest()
