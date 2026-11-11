import datetime as dt
import importlib
from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError
from django.utils.timezone import now

from eventyay.base.models import Room
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services import event as event_service
from eventyay.base.services import room as room_service


stream_schedule_migration = importlib.import_module(
    "eventyay.base.migrations.0034_migrate_native_stream_schedules"
)


async def _allow_permission(**kwargs):
    """Allow permission check in test async contexts."""
    return True


class ChannelLayer:
    """Mock channel layer for group messaging in tests."""

    async def group_send(self, *args, **kwargs):
        """Simulate group_send method of channel layer."""
        pass


def _patch_room_creation(monkeypatch):
    """Patch event_service._create_room and channel layer for unit tests."""
    created = {}

    async def fake_create_room(data, with_channel=False, **kwargs):
        created["data"] = data
        created["with_channel"] = with_channel
        channel = SimpleNamespace(id="channel-id") if with_channel else None
        return SimpleNamespace(id="room-id"), channel

    monkeypatch.setattr(event_service, "_create_room", fake_create_room)
    monkeypatch.setattr(event_service, "get_channel_layer", ChannelLayer)
    return created


def test_create_schedule_driven_stage_without_base_stream(monkeypatch):
    """Verify creating a schedule-driven stage without a base stream creates room with channel."""
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


def test_create_always_on_youtube_stage_stores_playback_flags(monkeypatch):
    """Verify creating an always-on YouTube stage properly persists playback flags."""
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id="event-id", has_permission_async=_allow_permission)

    async_to_sync(event_service.create_room)(
        event,
        {
            "name": "YouTube Stage",
            "description": "a description",
            "modules": [
                {
                    "type": "livestream.youtube",
                    "config": {
                        "playback_mode": "always_on",
                        "ytid": "dQw4w9WgXcQ",
                        "startMuted": True,
                        "enablePrivacyEnhancedMode": True,
                        "loop": True,
                        "modestBranding": True,
                        "hideControls": True,
                        "noRelated": True,
                        "disableKb": True,
                        "showInfo": True,
                    },
                },
            ],
        },
        object(),
    )

    livestream = next(
        m
        for m in created["data"]["module_config"]
        if m["type"] == "livestream.youtube"
    )
    assert livestream["config"] == {
        "playback_mode": "always_on",
        "ytid": "dQw4w9WgXcQ",
        "startMuted": True,
        "enablePrivacyEnhancedMode": True,
        "loop": True,
        "modestBranding": True,
        "hideControls": True,
        "noRelated": True,
        "disableKb": True,
        "showInfo": True,
    }


def test_create_always_on_hls_stage_stores_base_stream(monkeypatch):
    """Verify creating an always-on HLS stage properly persists the base HLS stream URL."""
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


def test_create_always_on_stage_stores_autostart_flags(monkeypatch):
    """Verify that always-on YouTube, Vimeo, and HLS stage creation preserves boolean and parsed autostart flags."""
    event = SimpleNamespace(id="event-id", has_permission_async=_allow_permission)

    cases = [
        (
            "livestream.youtube",
            {
                "playback_mode": "always_on",
                "ytid": "dQw4w9WgXcQ",
                "autoStart": False,
                "startMuted": True,
            },
            False,
        ),
        (
            "livestream.vimeo",
            {
                "playback_mode": "always_on",
                "url": "https://vimeo.com/123456789",
                "autoStart": "false",
            },
            False,
        ),
        (
            "livestream.native",
            {
                "playback_mode": "always_on",
                "hls_url": "https://example.com/live.m3u8",
                "autoStart": "true",
            },
            True,
        ),
    ]

    for module_type, config, expected_autostart in cases:
        created = _patch_room_creation(monkeypatch)
        async_to_sync(event_service.create_room)(
            event,
            {
                "name": f"{module_type} Stage",
                "description": "a description",
                "modules": [
                    {
                        "type": module_type,
                        "config": config,
                    },
                ],
            },
            object(),
        )

        mod = next(m for m in created["data"]["module_config"] if m["type"] == module_type)
        assert mod["config"]["autoStart"] is expected_autostart


def test_create_always_on_stage_rejects_invalid_autostart_flag(monkeypatch):
    """Verify that invalid autoStart values raise ValidationError."""
    event = SimpleNamespace(id="event-id", has_permission_async=_allow_permission)
    _patch_room_creation(monkeypatch)

    with pytest.raises(ValidationError):
        async_to_sync(event_service.create_room)(
            event,
            {
                "name": "Invalid Stage",
                "description": "a description",
                "modules": [
                    {
                        "type": "livestream.native",
                        "config": {
                            "playback_mode": "always_on",
                            "hls_url": "https://example.com/live.m3u8",
                            "autoStart": "not-a-boolean",
                        },
                    },
                ],
            },
            object(),
        )


def test_create_always_on_vimeo_stage_stores_playback_flags(monkeypatch):
    """Verify that Vimeo streams preserve all playback flags including autoStart, hideControls, and disableKb."""
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id="event-id", has_permission_async=_allow_permission)

    async_to_sync(event_service.create_room)(
        event,
        {
            "name": "Vimeo Stage",
            "description": "a description",
            "modules": [
                {
                    "type": "livestream.vimeo",
                    "config": {
                        "playback_mode": "always_on",
                        "url": "https://vimeo.com/123456789",
                        "autoStart": False,
                        "hideControls": True,
                        "disableKb": True,
                        "loop": True,
                        "dnt": True,
                    },
                },
            ],
        },
        object(),
    )

    livestream = next(
        m
        for m in created["data"]["module_config"]
        if m["type"] == "livestream.vimeo"
    )
    assert livestream["config"] == {
        "playback_mode": "always_on",
        "url": "https://vimeo.com/123456789",
        "autoStart": False,
        "hideControls": True,
        "disableKb": True,
        "loop": True,
        "dnt": True,
    }


@pytest.mark.django_db
def test_stream_schedule_choices_do_not_expose_native():
    """Verify StreamSchedule stream_type choices do not include native."""
    choices = [choice[0] for choice in StreamSchedule._meta.get_field("stream_type").choices]
    assert choices == ["youtube", "vimeo", "hls"]
    assert "native" not in choices


@pytest.mark.django_db
def test_native_stream_schedule_migration_maps_to_hls(event):
    """Verify migration maps legacy native stream_type to hls."""
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
    """Verify reverse migration for native stream schedules is a no-op."""
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
    """Verify stream schedules are cleared when a stage leaves schedule-driven mode."""
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

    async def fake_broadcast_upcoming_stream(room_id, stream_schedule):
        return None

    monkeypatch.setattr(
        room_service, "broadcast_stream_change", fake_broadcast_stream_change
    )
    monkeypatch.setattr(
        room_service, "broadcast_upcoming_stream", fake_broadcast_upcoming_stream
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
    """Verify stream schedules are retained when a stage remains schedule-driven."""
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
    """Verify uses_schedule_driven_stage detects schedule-driven stage modules."""
    assert room_service.uses_schedule_driven_stage(module_config) is expected
