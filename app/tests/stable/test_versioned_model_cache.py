import pickle
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from django_scopes import scope

from eventyay.base.models import Room


@pytest.mark.django_db
def test_room_pickle_excludes_related_event_settings(room, event):
    """Loaded Event.settings must not be pickled into the process cache."""
    with scope(event=event):
        room = Room.objects.select_related('event').get(pk=room.pk)
        _ = room.event.settings
        assert 'event' in room._state.fields_cache

        restored = pickle.loads(pickle.dumps(room))

    assert restored.pk == room.pk
    assert restored._state.fields_cache == {}


@pytest.mark.django_db
@pytest.mark.parametrize(
    'cache_error',
    [
        AttributeError('corrupt'),
        ImportError('missing module'),
        IndexError('truncated pickle'),
    ],
)
def test_refresh_drops_unreadable_process_cache(room, event, cache_error):
    with scope(event=event):
        room = Room.objects.get(pk=room.pk)
        original_version = room.version

        process_cache = MagicMock()
        process_cache.get.side_effect = cache_error
        process_cache.delete = MagicMock()
        process_cache.set = MagicMock()

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=str(original_version + 1).encode())
        redis.__aenter__ = AsyncMock(return_value=redis)
        redis.__aexit__ = AsyncMock(return_value=None)

        with (
            patch('eventyay.base.models.cache.caches') as caches_mock,
            patch('eventyay.base.models.cache.aredis', return_value=redis),
            patch.object(room, 'refresh_from_db') as refresh_from_db,
        ):
            caches_mock.__getitem__.return_value = process_cache
            room.version = original_version
            async_to_sync(room.refresh_from_db_if_outdated)()

        process_cache.delete.assert_called_once_with(room._cachekey)
        refresh_from_db.assert_called_once()
