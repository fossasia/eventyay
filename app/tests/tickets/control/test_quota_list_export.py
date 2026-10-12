import datetime

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.exporters.orderlist import QuotaListExporter
from eventyay.base.models import Event, Organizer, Quota, SubEvent


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        has_subevents=True,
    )
    event.settings.timezone = 'Europe/Berlin'
    return event


@pytest.mark.django_db
def test_quota_export_renders_subevent_dates_in_event_timezone(event):
    """
    The quota exporter must not crash on event series (has_subevents).

    Regression: Event.timezone is a CharField, so passing it straight to
    astimezone() raises TypeError (HTTP 500) instead of formatting the dates.
    """
    assert event.timezone == 'UTC'
    subevent = SubEvent.objects.create(
        event=event,
        name='Day one',
        date_from=datetime.datetime(2026, 5, 1, 9, 0, tzinfo=datetime.timezone.utc),
        date_to=datetime.datetime(2026, 5, 1, 18, 0, tzinfo=datetime.timezone.utc),
    )
    Quota.objects.create(event=event, name='Tickets', size=10, subevent=subevent)

    rows = list(QuotaListExporter(event).iterate_list({}))

    assert len(rows) == 2
    assert rows[0][-3:] == ['Date', 'Start date', 'End date']
    assert rows[1][0] == 'Tickets'
    assert rows[1][-3] == 'Day one'
    # 09:00 UTC is 11:00 in Europe/Berlin (CEST, UTC+2, in May)
    assert rows[1][-2] == '2026-05-01 11:00:00 CEST'
    assert rows[1][-1] == '2026-05-01 20:00:00 CEST'


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('timezone', 'start', 'end'),
    [
        ('America/Los_Angeles', '2026-04-30 17:30:00 PDT', '2026-04-30 19:00:00 PDT'),
        ('Asia/Tokyo', '2026-05-01 09:30:00 JST', '2026-05-01 11:00:00 JST'),
    ],
)
def test_quota_export_uses_ticketing_timezone_at_date_boundary(event, timezone, start, end):
    """Export local dates even when the model timezone stays at its UTC default."""
    with scope(event=event, organizer=event.organizer):
        assert event.timezone == 'UTC'
        event.settings.timezone = timezone
        subevent = SubEvent.objects.create(
            event=event,
            name='Day one',
            date_from=datetime.datetime(2026, 5, 1, 0, 30, tzinfo=datetime.timezone.utc),
            date_to=datetime.datetime(2026, 5, 1, 2, 0, tzinfo=datetime.timezone.utc),
        )
        Quota.objects.create(event=event, name='Tickets', size=10, subevent=subevent)

        rows = list(QuotaListExporter(event).iterate_list({}))

        assert rows[1][-2:] == [start, end]


@pytest.mark.django_db
def test_quota_export_without_subevent_has_no_date_columns(event):
    """A non-series event keeps the original header and adds no date columns."""
    event.has_subevents = False
    event.save()
    Quota.objects.create(event=event, name='Tickets', size=10)

    rows = list(QuotaListExporter(event).iterate_list({}))

    assert len(rows) == 2
    assert rows[0] == [
        'Quota name',
        'Total quota',
        'Paid orders',
        'Pending orders',
        'Blocking vouchers',
        "Current user's carts",
        'Waiting list',
        'Exited orders',
        'Current availability',
    ]
    assert rows[1][0] == 'Tickets'
