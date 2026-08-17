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
