import datetime as dt
import importlib
from types import SimpleNamespace

from contextlib import contextmanager
from unittest.mock import MagicMock
import pytest
from asgiref.sync import async_to_sync
from django.utils.timezone import now

from eventyay.base.models import Room
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services import event as event_service
from eventyay.base.services import room as room_service

stream_schedule_migration = importlib.import_module(
    "eventyay.base.migrations.0034_migrate_native_stream_schedules"
)


async def _allow_permission(**kwargs):
    return True


class ChannelLayer:
    async def group_send(self, *args, **kwargs):
        pass


def _patch_room_creation(monkeypatch):
    created = {}

    async def fake_create_room(data, with_channel=False, **kwargs):
        created["data"] = data
        created["with_channel"] = with_channel
        channel = SimpleNamespace(id="channel-id") if with_channel else None
        return SimpleNamespace(id="room-id"), channel

    monkeypatch.setattr(event_service, "_create_room", fake_create_room)
    monkeypatch.setattr(event_service, "get_channel_layer", lambda: ChannelLayer())
    return created


def test_create_schedule_driven_stage_without_base_stream(monkeypatch):
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id="event-id", has_permission_async=_allow_permission)

    result = async_to_sync(event_service.create_room)(
        event,
        {
            "name": "Schedule Driven Stage",
            "description": "a description",
            "modules": [
                {"type": "chat.native", "config": {"volatile": True}},
                {
                    "type": "livestream.native",
                    "config": {"playback_mode": "schedule_driven"},
                },
            ],
        },
        object(),
    )

    livestream = next(
        m
        for m in created["data"]["module_config"]
        if m["type"] == "livestream.native"
    )
    assert result == {"room": "room-id", "channel": "channel-id"}
    assert created["with_channel"] is True
    assert livestream["config"] == {"playback_mode": "schedule_driven"}


def test_create_always_on_hls_stage_stores_base_stream(monkeypatch):
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id="event-id", has_permission_async=_allow_permission)

    result = async_to_sync(event_service.create_room)(
        event,
        {
            "name": "Always On Stage",
            "description": "a description",
            "modules": [
                {
                    "type": "livestream.native",
                    "config": {
                        "playback_mode": "always_on",
                        "hls_url": "https://example.com/live.m3u8",
                    },
                },
            ],
        },
        object(),
    )

    livestream = next(
        m
        for m in created["data"]["module_config"]
        if m["type"] == "livestream.native"
    )
    assert result == {"room": "room-id", "channel": None}
    assert created["with_channel"] is False
    assert livestream["config"] == {
        "playback_mode": "always_on",
        "hls_url": "https://example.com/live.m3u8",
    }


@pytest.mark.django_db
def test_stream_schedule_choices_do_not_expose_native():
    choices = [choice[0] for choice in StreamSchedule._meta.get_field("stream_type").choices]
    assert choices == ["youtube", "vimeo", "hls", "iframe"]
    assert "native" not in choices


@pytest.mark.django_db
def test_native_stream_schedule_migration_maps_to_hls(event):
    room = Room.objects.create(event=event, name="Stage")
    schedule = StreamSchedule.objects.create(
        room=room,
        title="Legacy native stream",
        url="https://example.com/live.m3u8",
        start_time=now(),
        end_time=now() + dt.timedelta(hours=1),
        stream_type="hls",
    )
    StreamSchedule.objects.filter(pk=schedule.pk).update(stream_type="native")
    schedule.refresh_from_db()

    class Apps:
        @staticmethod
        def get_model(app_label, model_name):
            assert (app_label, model_name) == ("base", "StreamSchedule")
            return StreamSchedule

    stream_schedule_migration.migrate_native_stream_schedules(Apps, None)
    schedule.refresh_from_db()
    assert schedule.stream_type == "hls"


@pytest.mark.django_db
def test_native_stream_schedule_migration_reverse_is_noop(event):
    room = Room.objects.create(event=event, name="Stage")
    schedule = StreamSchedule.objects.create(
        room=room,
        title="HLS stream",
        url="https://example.com/live.m3u8",
        start_time=now(),
        end_time=now() + dt.timedelta(hours=1),
        stream_type="hls",
    )

    stream_schedule_migration.Migration.operations[0].reverse_code(None, None)

    schedule.refresh_from_db()
    assert schedule.stream_type == "hls"


@pytest.mark.django_db
def test_clear_stream_schedules_when_stage_leaves_schedule_driven(
    event, monkeypatch
):
    room = Room.objects.create(
        event=event,
        name="Stage",
        module_config=[
            {
                "type": "livestream.native",
                "config": {"playback_mode": "schedule_driven"},
            }
        ],
    )
    StreamSchedule.objects.create(
        room=room,
        title="HLS stream",
        url="https://example.com/live.m3u8",
        start_time=now(),
        end_time=now() + dt.timedelta(hours=1),
        stream_type="hls",
    )
    broadcasts = []

    async def fake_broadcast_stream_change(room_id, stream_schedule, reload=False):
        broadcasts.append((room_id, stream_schedule, reload))

    monkeypatch.setattr(
        room_service, "broadcast_stream_change", fake_broadcast_stream_change
    )

    room.module_config = [
        {
            "type": "livestream.native",
            "config": {"playback_mode": "always_on", "hls_url": ""},
        }
    ]
    cleared = room_service.clear_stream_schedules_unless_schedule_driven(room)

    assert cleared is True
    assert not StreamSchedule.objects.filter(room=room).exists()
    assert broadcasts == [(room.pk, None, True)]


@pytest.mark.django_db
def test_clear_stream_schedules_keeps_schedules_when_stage_stays_schedule_driven(
    event, monkeypatch
):
    room = Room.objects.create(
        event=event,
        name="Stage",
        module_config=[
            {
                "type": "livestream.native",
                "config": {"playback_mode": "schedule_driven"},
            }
        ],
    )
    schedule = StreamSchedule.objects.create(
        room=room,
        title="HLS stream",
        url="https://example.com/live.m3u8",
        start_time=now(),
        end_time=now() + dt.timedelta(hours=1),
        stream_type="hls",
    )
    broadcasts = []

    async def fake_broadcast_stream_change(room_id, stream_schedule, reload=False):
        broadcasts.append((room_id, stream_schedule, reload))

    monkeypatch.setattr(
        room_service, "broadcast_stream_change", fake_broadcast_stream_change
    )

    room.module_config = [
        {
            "type": "livestream.native",
            "config": {"playback_mode": "schedule_driven"},
        }
    ]
    cleared = room_service.clear_stream_schedules_unless_schedule_driven(room)

    assert cleared is False
    assert StreamSchedule.objects.filter(pk=schedule.pk).exists()
    assert broadcasts == []


@pytest.mark.parametrize(
    ("module_config", "expected"),
    [
        (None, False),
        ([], False),
        (
            [
                {
                    "type": "livestream.native",
                    "config": {"playback_mode": "schedule_driven"},
                }
            ],
            True,
        ),
        (
            [
                {
                    "type": "livestream.native",
                    "config": {"playback_mode": "always_on"},
                }
            ],
            False,
        ),
        (
            [
                {
                    "type": "chat.native",
                    "config": {"playback_mode": "schedule_driven"},
                }
            ],
            False,
        ),
    ],
)
def test_uses_schedule_driven_stage(module_config, expected):
    assert room_service.uses_schedule_driven_stage(module_config) is expected

def test_api_404_does_not_render_template(monkeypatch):
    from django.http import Http404
    from django.test import RequestFactory

    from eventyay.base.views.errors import page_not_found

    get_template = MagicMock()
    monkeypatch.setattr('eventyay.base.views.errors.get_template', get_template)
    response = page_not_found(RequestFactory().get('/api/v1/does-not-exist'), Http404())
    assert response.status_code == 404
    get_template.assert_not_called()


def test_html_404_still_renders_template(monkeypatch):
    from django.http import Http404
    from django.test import RequestFactory

    from eventyay.base.views.errors import page_not_found

    template = MagicMock()
    template.render.return_value = '<html>404</html>'
    monkeypatch.setattr('eventyay.base.views.errors.get_template', lambda name: template)
    response = page_not_found(RequestFactory().get('/missing-page'), Http404())
    assert response.status_code == 404
    template.render.assert_called_once()


@contextmanager
def overloaded_middleware(monkeypatch):
    from django.http import HttpResponse

    from eventyay.base import middleware as middleware_module
    from eventyay.base.middleware import LoadSheddingMiddleware

    monkeypatch.setattr(middleware_module, 'MAX_CONCURRENT_REQUESTS', 16)
    previous = LoadSheddingMiddleware.active_requests
    LoadSheddingMiddleware.active_requests = 16
    try:
        yield LoadSheddingMiddleware(lambda request: HttpResponse('ok'))
    finally:
        LoadSheddingMiddleware.active_requests = previous


def test_load_shedding_is_enabled_by_default():
    from eventyay.base.middleware import MAX_CONCURRENT_REQUESTS

    assert MAX_CONCURRENT_REQUESTS == 16


def test_load_shedding_can_be_disabled(monkeypatch):
    from django.http import HttpResponse
    from django.test import RequestFactory

    from eventyay.base import middleware as middleware_module
    from eventyay.base.middleware import LoadSheddingMiddleware

    monkeypatch.setattr(middleware_module, 'MAX_CONCURRENT_REQUESTS', 0)
    previous = LoadSheddingMiddleware.active_requests
    LoadSheddingMiddleware.active_requests = 10_000
    try:
        middleware = LoadSheddingMiddleware(lambda request: HttpResponse('ok'))
        assert middleware(RequestFactory().get('/schedule/')).status_code == 200
    finally:
        LoadSheddingMiddleware.active_requests = previous


def test_load_shedding_returns_503(monkeypatch):
    from django.test import RequestFactory

    with overloaded_middleware(monkeypatch) as middleware:
        response = middleware(RequestFactory().get('/schedule/'))
        assert response.status_code == 503
        assert response['Retry-After'] == '10'


@pytest.mark.parametrize(
    'path',
    [
        '/healthcheck/',
        '/api/v1/organizers/wm/checkin/redeem/',
        '/api/v1/organizers/wm/events/wm/checkinlists/1/positions/',
    ],
)
def test_load_shedding_exempts_checkin_and_health(path, monkeypatch):
    from django.test import RequestFactory

    with overloaded_middleware(monkeypatch) as middleware:
        assert middleware(RequestFactory().get(path)).status_code == 200

def test_heavy_celery_tasks_routed_to_longrunning():
    from django.conf import settings

    routes = settings.CELERY_TASK_ROUTES
    for name in (
        'eventyay.plugins.badges.tasks.*',
        'eventyay.base.services.export.*',
        'eventyay.base.services.orderimport.*',
        'eventyay.features.importers.tasks.*',
        'eventyay.base.services.tickets.generate',
        'pretalx.agenda.export_schedule_html',
    ):
        assert routes[name]['queue'] == 'longrunning'


def test_404_skips_session_save():
    from django.http import HttpResponse
    from django.test import RequestFactory

    from eventyay.common.middleware.domains import SessionMiddleware

    saved = []

    class FakeSession:
        accessed = True
        modified = False

        def is_empty(self):
            return False

        def save(self):
            saved.append(1)

    request = RequestFactory().get('/missing-page')
    request.session = FakeSession()
    middleware = SessionMiddleware(lambda req: HttpResponse(status=404))
    middleware.process_response(request, HttpResponse(status=404))
    assert saved == []
