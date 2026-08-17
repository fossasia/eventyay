from types import SimpleNamespace

from eventyay.base.services import event as event_service


def test_room_config_includes_current_stream(monkeypatch):
    monkeypatch.setattr(
        event_service,
        'get_room_current_stream_data',
        lambda room: {'url': 'https://example.com/live.m3u8'},
    )
    room = SimpleNamespace(
        id=1,
        name='Stage',
        description='',
        picture=None,
        import_id='',
        pretalx_id=None,
        force_join=False,
        schedule_data=None,
        module_config=[],
    )
    config = event_service.get_room_config(room, [])
    assert config['currentStream']['url'] == 'https://example.com/live.m3u8'


def test_room_current_stream_uses_serialize_helper(monkeypatch):
    stream = SimpleNamespace(
        pk=1,
        room_id=2,
        title='Live',
        url='https://example.com/live.m3u8',
        start_time=None,
        end_time=None,
        stream_type='hls',
        config={},
        created_at=None,
        updated_at=None,
    )
    room = SimpleNamespace(pk=2, get_current_stream=lambda: stream)

    monkeypatch.setattr(
        'eventyay.base.services.room.serialize_current_stream',
        lambda current: {'url': current.url, 'id': current.pk},
        raising=False,
    )
    monkeypatch.delattr('eventyay.base.services.room.get_cached_current_stream_data', raising=False)

    data = event_service.get_room_current_stream_data(room)
    assert data == {'url': 'https://example.com/live.m3u8', 'id': 1}


def test_batch_room_current_stream_data_uses_one_query(event, django_assert_num_queries):
    import datetime as dt

    from django.utils.timezone import now

    from eventyay.base.models import Room
    from eventyay.base.models.stream_schedule import StreamSchedule

    start = now() - dt.timedelta(minutes=5)
    end = now() + dt.timedelta(hours=1)
    room_a = Room.objects.create(event=event, name='Stage A')
    room_b = Room.objects.create(event=event, name='Stage B')
    StreamSchedule.objects.create(
        room=room_a,
        title='Live A',
        url='https://example.com/a.m3u8',
        start_time=start,
        end_time=end,
        stream_type='hls',
    )
    StreamSchedule.objects.create(
        room=room_b,
        title='Live B',
        url='https://example.com/b.m3u8',
        start_time=start,
        end_time=end,
        stream_type='hls',
    )

    with django_assert_num_queries(1):
        data = event_service.batch_room_current_stream_data([room_a, room_b])

    assert data[room_a.pk]['url'] == 'https://example.com/a.m3u8'
    assert data[room_b.pk]['url'] == 'https://example.com/b.m3u8'
