import datetime as dt
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models.stream_schedule import StreamSchedule


@pytest.mark.django_db
def test_stream_schedule_creation(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            title="Day 1 Stream",
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
            stream_type="youtube",
        )
        assert schedule.room == room
        assert schedule.title == "Day 1 Stream"
        assert schedule.url == "https://www.youtube.com/watch?v=test123"
        assert schedule.stream_type == "youtube"
        assert schedule.pk is not None


@pytest.mark.django_db
def test_stream_schedule_str_with_title(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            title="Keynotes",
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        assert str(schedule) == f"{room.name} - Keynotes"


@pytest.mark.django_db
def test_stream_schedule_str_without_title(room):
    with scope(event=room.event):
        start = now() + timedelta(hours=1)
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=start,
            end_time=now() + timedelta(hours=3),
        )
        assert str(schedule) == f"{room.name} - {start}"


@pytest.mark.django_db
def test_stream_schedule_validation_end_before_start(room):
    with scope(event=room.event):
        schedule = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=3),
            end_time=now() + timedelta(hours=1),
        )
        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()
        assert "end_time" in exc_info.value.message_dict


@pytest.mark.django_db
def test_stream_schedule_validation_end_equal_start(room):
    with scope(event=room.event):
        start = now() + timedelta(hours=1)
        schedule = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=start,
            end_time=start,
        )
        with pytest.raises(ValidationError) as exc_info:
            schedule.full_clean()
        assert "end_time" in exc_info.value.message_dict


@pytest.mark.django_db
def test_stream_schedule_overlap_validation_same_time(room):
    with scope(event=room.event):
        start = now() + timedelta(hours=1)
        end = now() + timedelta(hours=3)
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=start,
            end_time=end,
        )
        overlapping = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=start,
            end_time=end,
        )
        with pytest.raises(ValidationError) as exc_info:
            overlapping.full_clean()
        assert "overlaps" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_stream_schedule_overlap_validation_partial_overlap_start(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        overlapping = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=now() + timedelta(hours=2),
            end_time=now() + timedelta(hours=4),
        )
        with pytest.raises(ValidationError):
            overlapping.full_clean()


@pytest.mark.django_db
def test_stream_schedule_overlap_validation_partial_overlap_end(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        overlapping = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=now() + timedelta(minutes=30),
            end_time=now() + timedelta(hours=2),
        )
        with pytest.raises(ValidationError):
            overlapping.full_clean()


@pytest.mark.django_db
def test_stream_schedule_overlap_validation_contains(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        overlapping = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=now() + timedelta(minutes=30),
            end_time=now() + timedelta(hours=4),
        )
        with pytest.raises(ValidationError):
            overlapping.full_clean()


@pytest.mark.django_db
def test_stream_schedule_overlap_validation_contained(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        overlapping = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=now() + timedelta(hours=1, minutes=30),
            end_time=now() + timedelta(hours=2, minutes=30),
        )
        with pytest.raises(ValidationError):
            overlapping.full_clean()


@pytest.mark.django_db
def test_stream_schedule_no_overlap_adjacent(room):
    with scope(event=room.event):
        start1 = now() + timedelta(hours=1)
        end1 = now() + timedelta(hours=2)
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=start1,
            end_time=end1,
        )
        schedule2 = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=end1,
            end_time=now() + timedelta(hours=3),
        )
        schedule2.full_clean()
        schedule2.save()
        assert StreamSchedule.objects.filter(room=room).count() == 2


@pytest.mark.django_db
def test_stream_schedule_no_overlap_separate(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        schedule2 = StreamSchedule(
            room=room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=now() + timedelta(hours=3),
            end_time=now() + timedelta(hours=4),
        )
        schedule2.full_clean()
        schedule2.save()
        assert StreamSchedule.objects.filter(room=room).count() == 2


@pytest.mark.django_db
def test_stream_schedule_update_excludes_self(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        schedule.title = "Updated Title"
        schedule.full_clean()
        schedule.save()
        assert schedule.title == "Updated Title"


@pytest.mark.django_db
def test_stream_schedule_is_active_current(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
        assert schedule.is_active() is True


@pytest.mark.django_db
def test_stream_schedule_is_active_future(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        assert schedule.is_active() is False


@pytest.mark.django_db
def test_stream_schedule_is_active_past(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=3),
            end_time=now() - timedelta(hours=1),
        )
        assert schedule.is_active() is False


@pytest.mark.django_db
def test_stream_schedule_is_active_at_start_boundary(room):
    with scope(event=room.event):
        start = now()
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=start,
            end_time=now() + timedelta(hours=2),
        )
        assert schedule.is_active(start) is True


@pytest.mark.django_db
def test_stream_schedule_is_active_at_end_boundary(room):
    with scope(event=room.event):
        end = now() + timedelta(hours=2)
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now(),
            end_time=end,
        )
        assert schedule.is_active(end) is False


@pytest.mark.django_db
def test_stream_schedule_is_active_with_custom_time(room):
    with scope(event=room.event):
        custom_time = now() + timedelta(hours=1, minutes=30)
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        assert schedule.is_active(custom_time) is True


@pytest.mark.django_db
def test_stream_schedule_different_rooms_no_overlap(room, other_room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        schedule2 = StreamSchedule(
            room=other_room,
            url="https://www.youtube.com/watch?v=test456",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        schedule2.full_clean()
        schedule2.save()
        assert StreamSchedule.objects.filter(room=room).count() == 1
        assert StreamSchedule.objects.filter(room=other_room).count() == 1


@pytest.mark.django_db
def test_stream_schedule_config_field(room):
    with scope(event=room.event):
        config = {"video_id": "test123", "autoplay": True}
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
            config=config,
        )
        assert schedule.config == config


@pytest.mark.django_db
def test_stream_schedule_stream_type_choices(room):
    with scope(event=room.event):
        for stream_type in ["youtube", "vimeo", "hls", "iframe", "native"]:
            schedule = StreamSchedule.objects.create(
                room=room,
                url="https://example.com/stream",
                start_time=now() + timedelta(hours=1),
                end_time=now() + timedelta(hours=3),
                stream_type=stream_type,
            )
            assert schedule.stream_type == stream_type
            schedule.delete()


@pytest.mark.django_db
def test_stream_schedule_ordering(room):
    with scope(event=room.event):
        schedule3 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test3",
            start_time=now() + timedelta(hours=3),
            end_time=now() + timedelta(hours=4),
        )
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=2),
            end_time=now() + timedelta(hours=3),
        )
        schedules = list(StreamSchedule.objects.filter(room=room))
        assert schedules[0] == schedule1
        assert schedules[1] == schedule2
        assert schedules[2] == schedule3


@pytest.mark.django_db
def test_stream_schedule_cascade_delete(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        schedule_id = schedule.pk
        room.delete()
        assert not StreamSchedule.objects.filter(pk=schedule_id).exists()
