import datetime as dt
import importlib
from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from django.utils.timezone import now

from eventyay.api.views import room as room_api_view
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


def stream_configuration_url(event, room):
    return (
        f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/'
        f'rooms/{room.pk}/stream-configuration/'
    )


@pytest.mark.django_db
def test_stream_configuration_saves_one_stream_and_clears_schedules(
    event, organizer_client, monkeypatch, django_capture_on_commit_callbacks
):
    room = Room.objects.create(
        event=event,
        name='Stage',
        module_config=[
            {
                'type': 'livestream.native',
                'config': {'playback_mode': 'schedule_driven'},
            }
        ],
    )
    StreamSchedule.objects.create(
        room=room,
        title='Old stream',
        url='https://example.com/old.m3u8',
        start_time=now() + dt.timedelta(hours=1),
        end_time=now() + dt.timedelta(hours=2),
        stream_type='hls',
    )
    broadcasts = []
    notifications = []

    async def fake_broadcast(room_id, stream_schedule, reload=False):
        broadcasts.append((room_id, stream_schedule, reload))

    async def fake_notify(event_id):
        notifications.append(event_id)

    monkeypatch.setattr(room_api_view, 'broadcast_stream_change', fake_broadcast)
    monkeypatch.setattr(room_api_view, 'notify_event_change', fake_notify)

    with django_capture_on_commit_callbacks(execute=True):
        response = organizer_client.put(
            stream_configuration_url(event, room),
            data={
                'module_config': [
                    {
                        'type': 'livestream.native',
                        'config': {
                            'playback_mode': 'always_on',
                            'hls_url': 'https://example.com/live.m3u8',
                        },
                    }
                ],
                'schedules': [],
            },
            content_type='application/json',
        )

    assert response.status_code == 200
    room.refresh_from_db()
    assert room.module_config[0]['config'] == {
        'playback_mode': 'always_on',
        'hls_url': 'https://example.com/live.m3u8',
    }
    assert not StreamSchedule.objects.filter(room=room).exists()
    assert broadcasts == [(room.pk, None, True)]
    assert notifications == [event.pk]


@pytest.mark.django_db
def test_stream_configuration_rejects_overlap_without_partial_changes(
    event, organizer_client
):
    original_module_config = [
        {
            'type': 'livestream.native',
            'config': {
                'playback_mode': 'always_on',
                'hls_url': 'https://example.com/original.m3u8',
            },
        }
    ]
    room = Room.objects.create(
        event=event,
        name='Stage',
        module_config=original_module_config,
    )
    original_schedule = StreamSchedule.objects.create(
        room=room,
        title='Existing stream',
        url='https://example.com/existing.m3u8',
        start_time=now() + dt.timedelta(hours=5),
        end_time=now() + dt.timedelta(hours=6),
        stream_type='hls',
    )
    start = now() + dt.timedelta(hours=1)

    response = organizer_client.put(
        stream_configuration_url(event, room),
        data={
            'module_config': [
                {
                    'type': 'livestream.native',
                    'config': {'playback_mode': 'schedule_driven'},
                }
            ],
            'schedules': [
                {
                    'url': 'https://example.com/first.m3u8',
                    'start_time': start.isoformat(),
                    'end_time': (start + dt.timedelta(hours=2)).isoformat(),
                    'stream_type': 'hls',
                    'config': {},
                },
                {
                    'url': 'https://example.com/second.m3u8',
                    'start_time': (start + dt.timedelta(hours=1)).isoformat(),
                    'end_time': (start + dt.timedelta(hours=3)).isoformat(),
                    'stream_type': 'hls',
                    'config': {},
                },
            ],
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    room.refresh_from_db()
    assert room.module_config == original_module_config
    assert StreamSchedule.objects.filter(pk=original_schedule.pk).exists()


@pytest.mark.django_db
def test_stream_configuration_rejects_schedule_from_another_room(
    event, organizer_client
):
    room = Room.objects.create(
        event=event,
        name='Stage',
        module_config=[
            {
                'type': 'livestream.native',
                'config': {'playback_mode': 'schedule_driven'},
            }
        ],
    )
    other_room = Room.objects.create(event=event, name='Other stage')
    other_schedule = StreamSchedule.objects.create(
        room=other_room,
        url='https://example.com/other.m3u8',
        start_time=now() + dt.timedelta(hours=1),
        end_time=now() + dt.timedelta(hours=2),
        stream_type='hls',
    )

    response = organizer_client.put(
        stream_configuration_url(event, room),
        data={
            'module_config': [
                {
                    'type': 'livestream.native',
                    'config': {'playback_mode': 'schedule_driven'},
                }
            ],
            'schedules': [
                {
                    'id': other_schedule.pk,
                    'url': other_schedule.url,
                    'start_time': other_schedule.start_time.isoformat(),
                    'end_time': other_schedule.end_time.isoformat(),
                    'stream_type': other_schedule.stream_type,
                    'config': {},
                }
            ],
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert StreamSchedule.objects.filter(pk=other_schedule.pk).exists()
    assert not StreamSchedule.objects.filter(room=room).exists()
