import datetime as dt
from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models.stream_schedule import StreamSchedule


@pytest.mark.django_db
def test_room_get_current_stream_active(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
        current = room.get_current_stream()
        assert current is not None
        assert current.pk == schedule.pk


@pytest.mark.django_db
def test_room_get_current_stream_none(room):
    with scope(event=room.event):
        current = room.get_current_stream()
        assert current is None


@pytest.mark.django_db
def test_room_get_current_stream_future(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        current = room.get_current_stream()
        assert current is None


@pytest.mark.django_db
def test_room_get_current_stream_past(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=3),
            end_time=now() - timedelta(hours=1),
        )
        current = room.get_current_stream()
        assert current is None


@pytest.mark.django_db
def test_room_get_current_stream_multiple_returns_first(room):
    with scope(event=room.event):
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() - timedelta(hours=2),
            end_time=now() + timedelta(hours=2),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        current = room.get_current_stream()
        assert current is not None
        assert current.pk == schedule1.pk


@pytest.mark.django_db
def test_room_get_current_stream_with_custom_time(room):
    with scope(event=room.event):
        custom_time = now() + timedelta(hours=1, minutes=30)
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=2),
        )
        current = room.get_current_stream(at_time=custom_time)
        assert current is not None
        assert current.pk == schedule.pk


@pytest.mark.django_db
def test_room_get_next_stream_upcoming(room):
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        next_stream = room.get_next_stream()
        assert next_stream is not None
        assert next_stream.pk == schedule.pk


@pytest.mark.django_db
def test_room_get_next_stream_none(room):
    with scope(event=room.event):
        next_stream = room.get_next_stream()
        assert next_stream is None


@pytest.mark.django_db
def test_room_get_next_stream_past_only(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=3),
            end_time=now() - timedelta(hours=1),
        )
        next_stream = room.get_next_stream()
        assert next_stream is None


@pytest.mark.django_db
def test_room_get_next_stream_current_active(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=2),
            end_time=now() + timedelta(hours=4),
        )
        next_stream = room.get_next_stream()
        assert next_stream is not None
        assert next_stream.pk == schedule2.pk


@pytest.mark.django_db
def test_room_get_next_stream_returns_earliest(room):
    with scope(event=room.event):
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=2),
            end_time=now() + timedelta(hours=4),
        )
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
        next_stream = room.get_next_stream()
        assert next_stream is not None
        assert next_stream.pk == schedule1.pk


@pytest.mark.django_db
def test_room_get_next_stream_with_custom_time(room):
    with scope(event=room.event):
        custom_time = now() + timedelta(hours=1, minutes=30)
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=2),
            end_time=now() + timedelta(hours=4),
        )
        next_stream = room.get_next_stream(at_time=custom_time)
        assert next_stream is not None
        assert next_stream.pk == schedule.pk


@pytest.mark.django_db
def test_room_get_next_stream_excludes_current(room):
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() + timedelta(hours=2),
            end_time=now() + timedelta(hours=4),
        )
        next_stream = room.get_next_stream()
        assert next_stream is not None
        assert next_stream.pk == schedule2.pk
        assert next_stream.url == "https://www.youtube.com/watch?v=test2"
