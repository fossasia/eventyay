from types import SimpleNamespace

import pytest
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError

from eventyay.base.exporters.room_broadcast import (
    BROADCAST_MODULE_TYPES,
    VideoRoomBroadcastConfigurationExporter,
)
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services import event as event_service
from eventyay.base.services import room as room_service
from eventyay.core.permissions import Permission


async def _allow_permission(**kwargs):
    return True


async def _deny_permission(**kwargs):
    return False


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


def test_create_always_on_vimeo_stage_stores_clean_config(monkeypatch):
    created = _patch_room_creation(monkeypatch)
    event = SimpleNamespace(id="event-id", has_permission_async=_allow_permission)

    result = async_to_sync(event_service.create_room)(
        event,
        {
            "name": "Always On Vimeo Stage",
            "description": "Vimeo stage description",
            "modules": [
                {
                    "type": "livestream.vimeo",
                    "config": {
                        "playback_mode": "always_on",
                        "url": "https://vimeo.com/123456789",
                        "startMuted": True,
                        "dnt": True,
                        "loop": True,
                        "hideControls": True,
                        "disableKb": True,
                        "showInfo": True,
                        "password": "  secretpass  ",
                        "unknown_option": "should_be_stripped",
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
    assert result == {"room": "room-id", "channel": None}
    assert created["with_channel"] is False
    assert livestream["config"] == {
        "playback_mode": "always_on",
        "url": "https://vimeo.com/123456789",
        "startMuted": True,
        "dnt": True,
        "loop": True,
        "hideControls": True,
        "disableKb": True,
        "showInfo": True,
        "password": "secretpass",
    }
    assert "unknown_option" not in livestream["config"]


def test_create_vimeo_stage_permission_enforcement(monkeypatch):
    _patch_room_creation(monkeypatch)
    checked_permissions = []

    async def tracking_permission_checker(permission=None, **kwargs):
        checked_permissions.append(permission)
        return False

    event = SimpleNamespace(id="event-id", has_permission_async=tracking_permission_checker)

    with pytest.raises(ValidationError) as exc_info:
        async_to_sync(event_service.create_room)(
            event,
            {
                "name": "Unauthorized Vimeo Stage",
                "modules": [
                    {
                        "type": "livestream.vimeo",
                        "config": {"url": "https://vimeo.com/123456789"},
                    },
                ],
            },
            object(),
        )

    assert "This user is not allowed to create a room of this type." in str(exc_info.value)

    assert Permission.EVENT_ROOMS_CREATE_STAGE in checked_permissions


@pytest.mark.parametrize(
    ("module_config", "expected"),
    [
        (
            [
                {
                    "type": "livestream.vimeo",
                    "config": {"playback_mode": "schedule_driven"},
                }
            ],
            True,
        ),
        (
            [
                {
                    "type": "livestream.vimeo",
                    "config": {"playback_mode": "always_on"},
                }
            ],
            False,
        ),
        (
            [
                {
                    "type": "livestream.vimeo",
                    "config": {"url": "https://vimeo.com/123456"},
                }
            ],
            False,
        ),
    ],
)
def test_uses_schedule_driven_stage_vimeo(module_config, expected):
    assert room_service.uses_schedule_driven_stage(module_config) is expected


def test_stream_schedule_choices_include_vimeo():
    choices = [choice[0] for choice in StreamSchedule._meta.get_field("stream_type").choices]
    assert "vimeo" in choices
    assert choices == ["youtube", "vimeo", "hls"]


def test_room_broadcast_exporter_includes_vimeo():
    assert "livestream.vimeo" in BROADCAST_MODULE_TYPES
    exporter = VideoRoomBroadcastConfigurationExporter.__new__(VideoRoomBroadcastConfigurationExporter)
    inferred = exporter._inferred_room_type([{"type": "livestream.vimeo"}])
    assert inferred == "stage"
