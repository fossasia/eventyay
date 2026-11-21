"""Beat dispatches the single canonical periodic_task signal."""

# Import modules whose AppConfig.ready() may not load them, so the consolidation
# still proves @receiver(periodic_task) attaches to the canonical signal.
from eventyay.base.services import auth as base_auth  # noqa: F401
from eventyay.base.services import checkin as base_checkin  # noqa: F401
from eventyay.base.services import cleanup as base_cleanup  # noqa: F401
from eventyay.base.services import invoices as base_invoices  # noqa: F401
from eventyay.base.services import orders as base_orders  # noqa: F401
from eventyay.base.services import room as base_room  # noqa: F401
from eventyay.base.services import telemetry as base_telemetry  # noqa: F401
from eventyay.base.services import update_check as base_update_check  # noqa: F401
from eventyay.base.services import waitinglist as base_waitinglist  # noqa: F401
from eventyay.base.signals import periodic_task as base_periodic_task
from eventyay.common.signals import periodic_task as common_periodic_task
from eventyay.common.tasks import send_periodic_signal
from eventyay.core.management.commands.runperiodic import Command as RunPeriodicCommand
from eventyay.person import tasks as person_tasks  # noqa: F401


EXPECTED_CORE_RECEIVERS = frozenset({
    'eventyay.api.signals.cleanup_api_logs',
    'eventyay.api.signals.cleanup_webhook_logs',
    'eventyay.base.services.auth.close_inactive_staff_sessions',
    'eventyay.base.services.checkin.process_exit_all',
    'eventyay.base.services.cleanup.clean_cached_files',
    'eventyay.base.services.cleanup.clean_cached_tickets',
    'eventyay.base.services.cleanup.clean_cart_positions',
    'eventyay.base.services.cleanup.clearsessions',
    'eventyay.base.services.invoices.fetch_ecb_rates',
    'eventyay.base.services.orders.expire_orders',
    'eventyay.base.services.orders.send_download_reminders',
    'eventyay.base.services.orders.send_expiry_warnings',
    'eventyay.base.services.room.check_stream_schedule_changes',
    'eventyay.base.services.telemetry.run_telemetry',
    'eventyay.base.services.update_check.run_update_check',
    'eventyay.base.services.waitinglist.process_waitinglist',
    'eventyay.common.signals.process_scheduled_emails',
    'eventyay.event.services.clean_cached_files',
    'eventyay.event.services.periodic_event_services',
    'eventyay.person.tasks.refetch_gravatars',
    'eventyay.person.tasks.run_update_check',
})


def connected_receiver_names(signal):
    sync_receivers, async_receivers = signal._live_receivers(None)
    return [f'{func.__module__}.{func.__name__}' for func in (*sync_receivers, *async_receivers)]


def test_common_periodic_task_is_the_base_signal():
    assert common_periodic_task is base_periodic_task


def test_send_periodic_signal_reaches_receivers_from_either_import():
    received = []

    def common_receiver(signal, sender, **kwargs):
        received.append('common')

    def base_receiver(signal, sender, **kwargs):
        received.append('base')

    common_periodic_task.connect(common_receiver, weak=False)
    base_periodic_task.connect(base_receiver, weak=False)
    try:
        send_periodic_signal()
    finally:
        common_periodic_task.disconnect(common_receiver)
        base_periodic_task.disconnect(base_receiver)

    assert received.count('common') == 1
    assert received.count('base') == 1


def test_failing_receiver_does_not_stop_others():
    received = []

    def failing_receiver(signal, sender, **kwargs):
        received.append('fail')
        raise RuntimeError('boom')

    def later_receiver(signal, sender, **kwargs):
        received.append('later')

    base_periodic_task.connect(failing_receiver, weak=False)
    base_periodic_task.connect(later_receiver, weak=False)
    try:
        send_periodic_signal()
    finally:
        base_periodic_task.disconnect(failing_receiver)
        base_periodic_task.disconnect(later_receiver)

    assert received == ['fail', 'later']


def test_runperiodic_executes_async_receivers():
    ran = []

    async def async_periodic_job(signal, sender, **kwargs):
        ran.append('async')

    base_periodic_task.connect(async_periodic_job, weak=False)
    try:
        RunPeriodicCommand().handle(
            verbosity=1,
            tasks=f'{async_periodic_job.__module__}.{async_periodic_job.__name__}',
        )
    finally:
        base_periodic_task.disconnect(async_periodic_job)

    assert ran == ['async']


def test_core_receivers_are_registered_once_on_the_canonical_signal():
    names = connected_receiver_names(base_periodic_task)

    missing = EXPECTED_CORE_RECEIVERS.difference(names)
    assert missing == set(), f'Missing periodic_task receivers: {sorted(missing)}'

    for name in EXPECTED_CORE_RECEIVERS:
        assert names.count(name) == 1, f'{name} was registered {names.count(name)} times'


def test_common_alias_exposes_the_same_receivers():
    assert connected_receiver_names(common_periodic_task) == connected_receiver_names(base_periodic_task)
