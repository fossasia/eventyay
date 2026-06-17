import datetime as dt
import importlib

import pytest
from asgiref.sync import async_to_sync
from django.utils.timezone import now

from eventyay.base.models import Room
from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services.event import create_room

stream_schedule_migration = importlib.import_module(
    "eventyay.base.migrations.0031_migrate_native_stream_schedules"
)


@pytest.mark.django_db
def test_create_schedule_driven_stage_without_base_stream(event, user):
    user.event_grants.create(event=event, role="video_stage_manager")

    result = async_to_sync(create_room)(
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
        user,
    )

    room = Room.objects.get(pk=result["room"])
    livestream = next(m for m in room.module_config if m["type"] == "livestream.native")
    assert livestream["config"] == {"playback_mode": "schedule_driven"}


@pytest.mark.django_db
def test_create_always_on_hls_stage_stores_base_stream(event, user):
    user.event_grants.create(event=event, role="video_stage_manager")

    result = async_to_sync(create_room)(
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
        user,
    )

    room = Room.objects.get(pk=result["room"])
    livestream = next(m for m in room.module_config if m["type"] == "livestream.native")
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
        stream_type="native",
        skip_validation=True,
    )

    class Apps:
        @staticmethod
        def get_model(app_label, model_name):
            assert (app_label, model_name) == ("base", "StreamSchedule")
            return StreamSchedule

    stream_schedule_migration.migrate_native_stream_schedules(Apps, None)
    schedule.refresh_from_db()
    assert schedule.stream_type == "hls"
