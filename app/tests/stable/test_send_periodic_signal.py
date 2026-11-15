"""The beat task must reach receivers on both periodic_task signals."""

import pytest

from eventyay.base.signals import periodic_task as base_periodic_task
from eventyay.common.signals import periodic_task as common_periodic_task
from eventyay.common.tasks import send_periodic_signal


@pytest.fixture
def calls():
    received = []

    def common_receiver(signal, sender, **kwargs):
        received.append('common')

    def base_receiver(signal, sender, **kwargs):
        received.append('base')

    common_periodic_task.connect(common_receiver, weak=False)
    base_periodic_task.connect(base_receiver, weak=False)
    yield received
    common_periodic_task.disconnect(common_receiver)
    base_periodic_task.disconnect(base_receiver)


def test_send_periodic_signal_reaches_both_signals(calls):
    send_periodic_signal()

    assert 'common' in calls
    assert 'base' in calls


def test_failing_receiver_does_not_stop_others(calls):
    def failing_receiver(signal, sender, **kwargs):
        raise RuntimeError('boom')

    common_periodic_task.connect(failing_receiver, weak=False)
    try:
        send_periodic_signal()
    finally:
        common_periodic_task.disconnect(failing_receiver)

    assert 'base' in calls
