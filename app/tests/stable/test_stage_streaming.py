import datetime as dt
import importlib
from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from django.utils.timezone import now

from eventyay.base.models import Room
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services import event as event_service
from eventyay.base.services import room as room_service

stream_schedule_migration = importlib.import_module(
    "eventyay.base.migrations.0031_migrate_native_stream_schedules"
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
