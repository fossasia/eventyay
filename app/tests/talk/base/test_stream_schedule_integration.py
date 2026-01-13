from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models.stream_schedule import StreamSchedule


@pytest.mark.django_db
def test_multi_day_conference_scenario(room):
    with scope(event=room.event):
        day1_morning = StreamSchedule.objects.create(
            room=room,
            title="Day 1 Morning",
            url="https://www.youtube.com/watch?v=day1morning",
            start_time=now().replace(hour=9, minute=0, second=0, microsecond=0),
            end_time=now().replace(hour=12, minute=0, second=0, microsecond=0),
        )
        day1_afternoon = StreamSchedule.objects.create(
            room=room,
            title="Day 1 Afternoon",
            url="https://www.youtube.com/watch?v=day1afternoon",
            start_time=now().replace(hour=13, minute=0, second=0, microsecond=0),
            end_time=now().replace(hour=17, minute=0, second=0, microsecond=0),
        )
        day2_morning = StreamSchedule.objects.create(
            room=room,
            title="Day 2 Morning",
            url="https://www.youtube.com/watch?v=day2morning",
            start_time=(now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0),
            end_time=(now() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0),
        )
        assert StreamSchedule.objects.filter(room=room).count() == 3
        schedules = list(StreamSchedule.objects.filter(room=room))
        assert schedules[0] == day1_morning
        assert schedules[1] == day1_afternoon
        assert schedules[2] == day2_morning


@pytest.mark.django_db
def test_timezone_handling_utc_storage(room):
    with scope(event=room.event):
        utc_time = now()
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=utc_time,
            end_time=utc_time + timedelta(hours=2),
        )
        schedule.refresh_from_db()
        assert schedule.start_time.tzinfo is not None
        assert schedule.end_time.tzinfo is not None


@pytest.mark.django_db
def test_multiple_rooms_independent_schedules(room, other_room):
    with scope(event=room.event):
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=room1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        schedule2 = StreamSchedule.objects.create(
            room=other_room,
            url="https://www.youtube.com/watch?v=room2",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        assert StreamSchedule.objects.filter(room=room).count() == 1
        assert StreamSchedule.objects.filter(room=other_room).count() == 1
        assert room.get_current_stream() is None
        assert other_room.get_current_stream() is None
        assert schedule1.room == room
        assert schedule2.room == other_room


@pytest.mark.django_db
def test_stream_schedule_gap_between_streams(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=3),
            end_time=now() + timedelta(hours=4),
        )
        gap_time = now() + timedelta(hours=2, minutes=30)
        current = room.get_current_stream(at_time=gap_time)
        assert current is None
        next_stream = room.get_next_stream(at_time=gap_time)
        assert next_stream is not None
        assert next_stream.pk == schedule2.pk


@pytest.mark.django_db
def test_stream_schedule_all_types(room):
    with scope(event=room.event):
        stream_types = ["youtube", "vimeo", "hls", "iframe", "native"]
        for i, stream_type in enumerate(stream_types):
            StreamSchedule.objects.create(
                room=room,
                url=f"https://example.com/stream{i}",
                start_time=now() + timedelta(hours=i),
                end_time=now() + timedelta(hours=i + 1),
                stream_type=stream_type,
            )
        assert StreamSchedule.objects.filter(room=room).count() == len(stream_types)
        for stream_type in stream_types:
            assert StreamSchedule.objects.filter(room=room, stream_type=stream_type).exists()


@pytest.mark.django_db
def test_stream_schedule_with_config(room):
    with scope(event=room.event):
        config = {
            "video_id": "test123",
            "autoplay": True,
            "mute": False,
            "language": "en",
        }
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
            config=config,
        )
        schedule.refresh_from_db()
        assert schedule.config == config
        assert schedule.config["video_id"] == "test123"
        assert schedule.config["autoplay"] is True


@pytest.mark.django_db
def test_stream_schedule_boundary_conditions(room):
    with scope(event=room.event):
        start = now() + timedelta(seconds=1)
        end = now() + timedelta(seconds=2)
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=start,
            end_time=end,
        )
        assert schedule.is_active(start) is True
        assert schedule.is_active(end) is False
        assert schedule.is_active(start + timedelta(milliseconds=500)) is True
        assert schedule.is_active(end - timedelta(milliseconds=1)) is True


@pytest.mark.django_db
def test_stream_schedule_ordering_multiple_days(room):
    with scope(event=room.event):
        day3 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=day3",
            start_time=now() + timedelta(days=2),
            end_time=now() + timedelta(days=2, hours=8),
        )
        day1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=day1",
            start_time=now() + timedelta(days=0),
            end_time=now() + timedelta(days=0, hours=8),
        )
        day2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=day2",
            start_time=now() + timedelta(days=1),
            end_time=now() + timedelta(days=1, hours=8),
        )
        schedules = list(StreamSchedule.objects.filter(room=room))
        assert schedules[0] == day1
        assert schedules[1] == day2
        assert schedules[2] == day3


@pytest.mark.django_db
def test_stream_schedule_room_cascade_delete(room):
    with scope(event=room.event):
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=3),
            end_time=now() + timedelta(hours=4),
        )
        schedule_ids = [schedule1.pk, schedule2.pk]
        room.delete()
        assert not StreamSchedule.objects.filter(pk__in=schedule_ids).exists()


@pytest.mark.django_db
def test_stream_schedule_current_vs_next_transition(room):
    with scope(event=room.event):
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(minutes=30),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        current = room.get_current_stream()
        assert current is not None
        assert current.pk == schedule1.pk
        next_stream = room.get_next_stream()
        assert next_stream is not None
        assert next_stream.pk == schedule2.pk
