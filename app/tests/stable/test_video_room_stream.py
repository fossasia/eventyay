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
