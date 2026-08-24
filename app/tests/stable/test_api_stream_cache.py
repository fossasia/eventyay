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

    with django_capture_on_commit_callbacks(execute=True):
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

    data, etag = get_cached_catalog_list(7, 'tracks', 'all', loader)
    cached, cached_etag = get_cached_catalog_list(7, 'tracks', 'all', loader)
    assert data == cached
    assert etag == cached_etag
    assert etag
    assert calls == [1]


@override_settings(CACHES=LOCMEM_CACHE)
def test_catalog_list_cache_scopes_by_locale():
    from eventyay.base.services.stale_cache import get_cached_catalog_list

    en_calls = []
    de_calls = []

    data_en, _ = get_cached_catalog_list(
        7,
        'tracks',
        'en',
        lambda: en_calls.append(1) or [{'id': 1, 'name': 'English'}],
    )
    data_de, _ = get_cached_catalog_list(
        7,
        'tracks',
        'de',
        lambda: de_calls.append(1) or [{'id': 1, 'name': 'Deutsch'}],
    )
    assert data_en != data_de
    assert en_calls == [1]
    assert de_calls == [1]

    get_cached_catalog_list(
        7,
        'tracks',
        'en',
        lambda: en_calls.append(1) or [{'id': 1, 'name': 'English'}],
    )
    assert en_calls == [1]


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_catalog_cache_invalidates_on_track_save(event, django_capture_on_commit_callbacks):
    from django.core.cache import cache

    from eventyay.base.models import Track
    from eventyay.base.services.stale_cache import get_cached_catalog_list

    cache.clear()
    calls = []

    def loader():
        calls.append(1)
        return [{'id': 1, 'name': 'Track A'}]

    get_cached_catalog_list(event.pk, 'tracks', 'all', loader)
    assert calls == [1]

    with django_capture_on_commit_callbacks(execute=True):
        Track.objects.create(event=event, name={'en': 'New Track'}, color='#ff0000')

    get_cached_catalog_list(event.pk, 'tracks', 'all', loader)
    assert calls == [1, 1]


def test_schedule_cache_user_scope_public_for_anonymous():
    from types import SimpleNamespace

    from django.contrib.auth.models import AnonymousUser

    from eventyay.talk_rules.tracks import schedule_cache_user_scope

    event = SimpleNamespace()
    assert schedule_cache_user_scope(event, AnonymousUser()) == 'public'


def test_schedule_retrieve_cache_skips_orga_view():
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from eventyay.api.views.schedule import ScheduleViewSet

    view = ScheduleViewSet()
    view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
    view.event = SimpleNamespace(pk=1)
    view.kwargs = {'pk': '5'}
    view.has_perm = MagicMock(side_effect=lambda perm, obj=None: perm == 'orga_view')

    assert view._schedule_cache_scope() is None


@override_settings(CACHES=LOCMEM_CACHE)
def test_video_spa_schedule_cache_avoids_repeat_build():
    from django.core.cache import cache

    from eventyay.base.services.stale_cache import get_cached_video_spa_schedule

    cache.clear()
    calls = []

    def loader():
        calls.append(1)
        return {'talks': [{'id': 1}]}

    first = get_cached_video_spa_schedule(7, 11, 'feat', loader)
    second = get_cached_video_spa_schedule(7, 11, 'feat', loader)
    featured_off = get_cached_video_spa_schedule(7, 11, 'nofeat', loader)
    assert first == second == {'talks': [{'id': 1}]}
    assert featured_off == first
    assert calls == [1, 1]


def test_talk_slots_filter_key_includes_ordering():
    from django.test import RequestFactory

    from eventyay.base.services.stale_cache import talk_slots_filter_key

    factory = RequestFactory()
    default = talk_slots_filter_key(factory.get('/'), ['room'])
    ordered = talk_slots_filter_key(factory.get('/?ordering=-start'), ['room'])
    assert default != ordered


def test_talk_slots_filter_key_includes_page():
    from django.test import RequestFactory

    from eventyay.base.services.stale_cache import talk_slots_filter_key

    factory = RequestFactory()
    page1 = talk_slots_filter_key(factory.get('/'), ['room'])
    page2 = talk_slots_filter_key(factory.get('/?page=2'), ['room'])
    assert page1 != page2


def test_catalog_list_cache_skips_paginated_viewsets():
    from types import SimpleNamespace

    from rest_framework.pagination import LimitOffsetPagination

    from eventyay.api.mixins import CachedCatalogListMixin
    from eventyay.api.views.submission import TrackViewSet

    class PaginatedCatalog(CachedCatalogListMixin):
        catalog_name = 'tracks'
        pagination_class = LimitOffsetPagination
        event = SimpleNamespace(pk=1)
        request = SimpleNamespace(query_params={})

    class UnpaginatedCatalog(CachedCatalogListMixin):
        catalog_name = 'tracks'
        event = SimpleNamespace(pk=1)
        request = SimpleNamespace(query_params={})

    class SearchedCatalog(CachedCatalogListMixin):
        catalog_name = 'tracks'
        event = SimpleNamespace(pk=1)
        request = SimpleNamespace(query_params={'search': 'keynote'})

    assert PaginatedCatalog().uses_catalog_list_cache() is False
    assert UnpaginatedCatalog().uses_catalog_list_cache() is True
    assert SearchedCatalog().uses_catalog_list_cache() is False
    assert CachedCatalogListMixin.pagination_class is None
    assert TrackViewSet.pagination_class is None


def test_room_list_stays_paginated_and_uncached():
    from eventyay.api.mixins import CachedCatalogListMixin
    from eventyay.api.views.room import RoomPagination, RoomViewSet

    assert RoomViewSet.pagination_class is RoomPagination
    assert not issubclass(RoomViewSet, CachedCatalogListMixin)


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_schedule_cache_invalidates_on_room_save(event):
    from unittest.mock import patch

    with patch('eventyay.base.services.stale_cache.bump_schedule_cache_version_on_commit') as bump:
        Room.objects.create(event=event, name='Hall A')

    bump.assert_called_with(event.pk)


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_schedule_cache_skips_speaker_profile_without_released_slot(event, user):
    from unittest.mock import patch
    from django_scopes import scope

    from eventyay.base.models.profile import SpeakerProfile

    with patch('eventyay.base.services.stale_cache.bump_schedule_cache_version_on_commit') as bump:
        with scope(event=event):
            SpeakerProfile.objects.create(user=user, event=event, biography='Draft bio')

    bump.assert_not_called()


@pytest.mark.django_db
@override_settings(CACHES=LOCMEM_CACHE)
def test_schedule_cache_invalidates_on_speaker_profile_save(event, user):
    from unittest.mock import patch
    from django_scopes import scope

    from eventyay.base.models import Schedule, Submission, SubmissionType, TalkSlot
    from eventyay.base.models.profile import SpeakerProfile

    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        submission = Submission.objects.create(
            event=event,
            title='Keynote',
            submission_type=submission_type,
        )
        submission.speakers.add(user)
        room = Room.objects.create(event=event, name='Main')
        schedule = Schedule.objects.create(event=event, version='v1')
        TalkSlot.objects.create(
            room=room,
            schedule=schedule,
            submission=submission,
            is_visible=True,
        )
        profile = SpeakerProfile.objects.create(user=user, event=event, biography='Old bio')

    with patch('eventyay.base.services.stale_cache.bump_schedule_cache_version_on_commit') as bump:
        with scope(event=event):
            profile.biography = 'Updated bio'
            profile.save(update_fields=['biography'])

    bump.assert_called_with(event.pk)


def test_talk_slots_cached_list_returns_paginated_envelope():
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory

    from eventyay.api.views.schedule import TalkSlotViewSet

    page_results = [{'id': index, 'submission': f'talk-{index}'} for index in range(1, 4)]
    paginated = {
        'count': 120,
        'next': 'http://example.com/slots/?page=2',
        'previous': None,
        'results': page_results,
    }
    request = RequestFactory().get('/slots/')
    request.user = AnonymousUser()
    request.query_params = request.GET

    view = TalkSlotViewSet()
    view.request = request
    view.format_kwarg = None
    view.event = SimpleNamespace(pk=1, current_schedule=SimpleNamespace(pk=1))
    view.action = 'list'
    view.is_orga = False
    view.filterset_class = MagicMock(get_fields=lambda: {})

    with patch(
        'eventyay.api.views.schedule.get_cached_talk_slots_list',
        return_value=(paginated, 'etag-value'),
    ) as cached:
        response = view.list(request)

    cached.assert_called_once()
    assert response.status_code == 200
    assert response.data['count'] == 120
    assert len(response.data['results']) == 3
    assert response.data['results'][0]['id'] == 1
    assert response['ETag'] == '"etag-value"'
