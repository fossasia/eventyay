from datetime import timedelta
from unittest.mock import patch

import pytest
from channels.layers import InMemoryChannelLayer
from django.core.cache import cache
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models.stream_schedule import StreamSchedule
from eventyay.base.services.room import broadcast_stream_change, check_stream_schedule_changes


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_broadcast_stream_change_with_stream(room):
    channel_layer = InMemoryChannelLayer()
    with patch("eventyay.base.services.room.get_channel_layer", return_value=channel_layer):
        with scope(event=room.event):
            schedule = StreamSchedule.objects.create(
                room=room,
                url="https://www.youtube.com/watch?v=test123",
                start_time=now() - timedelta(hours=1),
                end_time=now() + timedelta(hours=1),
            )
        await broadcast_stream_change(room.pk, schedule, reload=True)
        group_name = f"room.{room.pk}"
        message = await channel_layer.receive(group_name)
        assert message["type"] == "stream.change"
        assert message["reload"] is True
        assert message["stream"] is not None
        assert message["stream"]["url"] == "https://www.youtube.com/watch?v=test123"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_broadcast_stream_change_without_stream(room):
    channel_layer = InMemoryChannelLayer()
    with patch("eventyay.base.services.room.get_channel_layer", return_value=channel_layer):
        await broadcast_stream_change(room.pk, None, reload=True)
        group_name = f"room.{room.pk}"
        message = await channel_layer.receive(group_name)
        assert message["type"] == "stream.change"
        assert message["reload"] is True
        assert message["stream"] is None


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_broadcast_stream_change_reload_false(room):
    channel_layer = InMemoryChannelLayer()
    with patch("eventyay.base.services.room.get_channel_layer", return_value=channel_layer):
        with scope(event=room.event):
            schedule = StreamSchedule.objects.create(
                room=room,
                url="https://www.youtube.com/watch?v=test123",
                start_time=now() - timedelta(hours=1),
                end_time=now() + timedelta(hours=1),
            )
        await broadcast_stream_change(room.pk, schedule, reload=False)
        group_name = f"room.{room.pk}"
        message = await channel_layer.receive(group_name)
        assert message["type"] == "stream.change"
        assert message["reload"] is False


@pytest.mark.django_db
def test_check_stream_schedule_changes_new_stream(room):
    cache.clear()
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
    with patch("eventyay.base.services.room.broadcast_stream_change") as mock_broadcast:
        check_stream_schedule_changes(sender=None)
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == str(room.pk)
        assert call_args[0][1].pk == schedule.pk
        assert call_args[0][2] is False


@pytest.mark.django_db
def test_check_stream_schedule_changes_no_current_stream(room):
    cache.clear()
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() + timedelta(hours=1),
            end_time=now() + timedelta(hours=3),
        )
    with patch("eventyay.base.services.room.broadcast_stream_change") as mock_broadcast:
        check_stream_schedule_changes(sender=None)
        cache_key = f"room:{room.pk}:last_broadcast_stream"
        last_broadcast_id = cache.get(cache_key)
        assert last_broadcast_id is None


@pytest.mark.django_db
def test_check_stream_schedule_changes_stream_ended(room):
    cache.clear()
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=2),
            end_time=now() - timedelta(hours=1),
        )
    cache_key = f"room:{room.pk}:last_broadcast_stream"
    cache.set(cache_key, schedule.pk, 300)
    with patch("eventyay.base.services.room.broadcast_stream_change") as mock_broadcast:
        check_stream_schedule_changes(sender=None)
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == str(room.pk)
        assert call_args[0][1] is None
        assert call_args[0][2] is True


@pytest.mark.django_db
def test_check_stream_schedule_changes_no_change(room):
    cache.clear()
    with scope(event=room.event):
        schedule = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
    cache_key = f"room:{room.pk}:last_broadcast_stream"
    cache.set(cache_key, schedule.pk, 300)
    with patch("eventyay.base.services.room.broadcast_stream_change") as mock_broadcast:
        check_stream_schedule_changes(sender=None)
        mock_broadcast.assert_not_called()


@pytest.mark.django_db
def test_check_stream_schedule_changes_stream_switched(room):
    cache.clear()
    with scope(event=room.event):
        schedule1 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() - timedelta(hours=2),
            end_time=now() - timedelta(hours=1),
        )
        schedule2 = StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
    cache_key = f"room:{room.pk}:last_broadcast_stream"
    cache.set(cache_key, schedule1.pk, 300)
    with patch("eventyay.base.services.room.broadcast_stream_change") as mock_broadcast:
        check_stream_schedule_changes(sender=None)
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        assert call_args[0][0] == str(room.pk)
        assert call_args[0][1].pk == schedule2.pk
        assert call_args[0][2] is False


@pytest.mark.django_db
def test_check_stream_schedule_changes_multiple_rooms(room, other_room):
    cache.clear()
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test1",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
        StreamSchedule.objects.create(
            room=other_room,
            url="https://www.youtube.com/watch?v=test2",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
    with patch("eventyay.base.services.room.broadcast_stream_change") as mock_broadcast:
        check_stream_schedule_changes(sender=None)
        assert mock_broadcast.call_count == 2
        call_room_ids = [call[0][0] for call in mock_broadcast.call_args_list]
        assert str(room.pk) in call_room_ids
        assert str(other_room.pk) in call_room_ids


@pytest.mark.django_db
def test_check_stream_schedule_changes_deleted_room(room):
    cache.clear()
    with scope(event=room.event):
        StreamSchedule.objects.create(
            room=room,
            url="https://www.youtube.com/watch?v=test123",
            start_time=now() - timedelta(hours=1),
            end_time=now() + timedelta(hours=1),
        )
        room.deleted = True
        room.save()
    with patch("eventyay.base.services.room.broadcast_stream_change") as mock_broadcast:
        check_stream_schedule_changes(sender=None)
        mock_broadcast.assert_not_called()
