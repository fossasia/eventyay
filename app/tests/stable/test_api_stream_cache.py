import datetime as dt
from types import SimpleNamespace

import pytest
from django.test.utils import override_settings
from django.utils.timezone import now

from eventyay.base.models import Room
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services import room as room_service

LOCMEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'api-stream-cache-tests',
    }
}


def _fake_stream():
    stamp = now()
    return SimpleNamespace(
        pk=9,
        room_id=3,
        title='Live',
        url='https://example.com/live.m3u8',
        start_time=stamp,
        end_time=stamp + dt.timedelta(hours=1),
        stream_type='hls',
        config={},
        created_at=stamp,
        updated_at=stamp,
    )


@override_settings(CACHES=LOCMEM_CACHE)
def test_cached_current_stream_avoids_repeat_query():
    from django.core.cache import cache

    cache.clear()
    stream = _fake_stream()
    room = SimpleNamespace(pk=3, get_current_stream=lambda: stream)

    data = room_service.get_cached_current_stream_data(room)
    assert data['url'] == 'https://example.com/live.m3u8'

    room.get_current_stream = lambda: (_ for _ in ()).throw(AssertionError('db'))
    cached = room_service.get_cached_current_stream_data(room)
    assert cached['url'] == 'https://example.com/live.m3u8'


@override_settings(CACHES=LOCMEM_CACHE)
def test_invalidate_current_stream_cache_forces_lookup():
    from django.core.cache import cache

    cache.clear()
    stream = _fake_stream()
    lookups = []

    def lookup():
        lookups.append(1)
        return stream

    room = SimpleNamespace(pk=3, get_current_stream=lookup)
    room_service.get_cached_current_stream_data(room)
    room_service.invalidate_current_stream_cache(3)
    room_service.get_cached_current_stream_data(room)
    assert lookups == [1, 1]


def test_current_stream_response_sets_cache_headers_and_etag():
    from django.test import RequestFactory

    from eventyay.api.views.room import current_stream_http_response

    data = {'id': 9, 'updated_at': '2026-08-15T10:00:00+00:00', 'url': 'https://example.com/live.m3u8'}
    response = current_stream_http_response(RequestFactory().get('/'), data)
    assert response.status_code == 200
    assert 'max-age=30' in response['Cache-Control']
    assert 'public' in response['Cache-Control']
    assert response['ETag']
    assert response['Last-Modified']

    not_modified = current_stream_http_response(
        RequestFactory().get('/', HTTP_IF_NONE_MATCH=response['ETag']),
        data,
    )
    assert not_modified.status_code == 304


def test_current_stream_authenticated_response_is_not_stored():
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory

    from eventyay.api.views.room import current_stream_http_response

    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    request.auth = object()
    response = current_stream_http_response(request, {'id': 1, 'updated_at': '2026-08-15T10:00:00+00:00'})
    assert 'no-store' in response['Cache-Control']


def test_current_stream_anonymous_session_cookie_may_be_cached():
    from django.conf import settings
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory

    from eventyay.api.views.room import current_stream_http_response

    request = RequestFactory().get('/')
    request.user = AnonymousUser()
    request.auth = None
    request.COOKIES[settings.SESSION_COOKIE_NAME] = 'anonymous-session'
    response = current_stream_http_response(request, {'id': 1, 'updated_at': '2026-08-15T10:00:00+00:00'})
    assert 'public' in response['Cache-Control']
    assert 'max-age=30' in response['Cache-Control']


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_stream_schedule_cache_invalidation_runs_on_commit(event, django_capture_on_commit_callbacks):
    from django.core.cache import cache
    from django.db import transaction

    cache.clear()
    room = Room.objects.create(event=event, name='Stage')
    start = now() - dt.timedelta(minutes=5)
    end = now() + dt.timedelta(hours=1)
    schedule = StreamSchedule.objects.create(
        room=room,
        title='Live',
        url='https://example.com/live.m3u8',
        start_time=start,
        end_time=end,
        stream_type='hls',
    )
    key = room_service.current_stream_cache_key(room.pk)
    room_service.get_cached_current_stream_data(room)
    assert cache.get(key) is not None

    with django_capture_on_commit_callbacks:
        with transaction.atomic():
            schedule.url = 'https://example.com/new.m3u8'
            schedule.save(update_fields=['url'])
            assert cache.get(key) is not None

    assert cache.get(key) is None
    assert cache.get(room_service.current_stream_stale_cache_key(room.pk)) is None


@override_settings(CACHES=LOCMEM_CACHE)
def test_stale_current_stream_served_when_db_unavailable():
    from django.core.cache import cache
    from django.db import OperationalError

    cache.clear()
    stream = _fake_stream()
    room = SimpleNamespace(pk=3, get_current_stream=lambda: stream)
    room_service.get_cached_current_stream_data(room)
    cache.delete(room_service.current_stream_cache_key(3))
    room.get_current_stream = lambda: (_ for _ in ()).throw(OperationalError('db unavailable'))

    data = room_service.get_cached_current_stream_data(room)
    assert data['url'] == 'https://example.com/live.m3u8'


@override_settings(CACHES=LOCMEM_CACHE)
def test_stale_next_stream_served_when_db_unavailable():
    from django.core.cache import cache
    from django.db import OperationalError

    cache.clear()
    stream = _fake_stream()
    room = SimpleNamespace(pk=4, get_next_stream=lambda: stream)
    room_service.get_cached_next_stream_data(room)
    cache.delete(room_service.next_stream_cache_key(4))
    room.get_next_stream = lambda: (_ for _ in ()).throw(OperationalError('db unavailable'))

    data = room_service.get_cached_next_stream_data(room)
    assert data['url'] == 'https://example.com/live.m3u8'


@override_settings(CACHES=LOCMEM_CACHE)
def test_catalog_list_cache_avoids_repeat_serialization():
    from eventyay.base.services.stale_cache import get_cached_catalog_list

    calls = []

    def loader():
        calls.append(1)
        return [{'id': 1, 'name': 'Track A'}]

    data, etag = get_cached_catalog_list(7, 'tracks', loader)
    cached, cached_etag = get_cached_catalog_list(7, 'tracks', loader)
    assert data == cached
    assert etag == cached_etag
    assert etag
    assert calls == [1]


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_catalog_cache_invalidates_on_track_save(event, django_capture_on_commit_callbacks):
    from django.core.cache import cache

    from eventyay.base.models import Track
    from eventyay.base.services.stale_cache import catalog_cache_keys, get_cached_catalog_list

    cache.clear()
    hot_key, _ = catalog_cache_keys(event.pk, 'tracks')

    def loader():
        return [{'id': 1, 'name': 'Track A'}]

    get_cached_catalog_list(event.pk, 'tracks', loader)
    assert cache.get(hot_key) is not None

    with django_capture_on_commit_callbacks:
        Track.objects.create(event=event, name={'en': 'New Track'}, color='#ff0000')

    assert cache.get(hot_key) is None


def test_schedule_cache_user_scope_public_for_anonymous():
    from types import SimpleNamespace

    from django.contrib.auth.models import AnonymousUser

    from eventyay.talk_rules.tracks import schedule_cache_user_scope

    event = SimpleNamespace()
    assert schedule_cache_user_scope(event, AnonymousUser()) == 'public'


def test_talk_slots_filter_key_includes_ordering():
    from django.test import RequestFactory

    from eventyay.base.services.stale_cache import talk_slots_filter_key

    factory = RequestFactory()
    default = talk_slots_filter_key(factory.get('/'), ['room'])
    ordered = talk_slots_filter_key(factory.get('/?ordering=-start'), ['room'])
    assert default != ordered
