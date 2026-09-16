"""Tests for the periodic stream-schedule receiver in eventyay.base.services.room.

`check_stream_schedule_changes` calls `cache.get()` and `cache.set()`, but the module never
imported `cache`. The function is a `@receiver(signal=periodic_task)`, and that signal is sent
once a minute by the `send_periodic_signal` Celery beat task via `Signal.send()`, which does
not swallow receiver exceptions. On any deployment with a room that has a stream schedule the
NameError therefore aborted the whole periodic run, skipping every receiver dispatched after
this one - and there are 21 of them, including order and invoice cleanup.

These tests need no database: the Room queryset is mocked and the test cache backend is
DummyCache, so `cache.get()` returns None and the broadcast branch is not taken.
"""

from unittest import mock

from eventyay.base.services import room as room_service


def test_room_service_has_cache_bound():
    """check_stream_schedule_changes dereferences `cache`; the name has to be bound."""
    assert hasattr(room_service, 'cache')


def test_check_stream_schedule_changes_runs_for_a_scheduled_room():
    """Regression: the loop body raised NameError on its first `cache.get()`."""
    room = mock.Mock(pk=4242)
    room.get_current_stream.return_value = None

    with mock.patch.object(room_service, 'Room') as room_model:
        queryset = room_model.objects.filter.return_value.select_related.return_value.distinct
        queryset.return_value = [room]

        room_service.check_stream_schedule_changes(sender=None)

    room.get_current_stream.assert_called_once()
