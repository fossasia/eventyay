from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.test import override_settings
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team, User


@pytest.fixture
@scopes_disabled()
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=datetime(2027, 2, 1, 9, 0, tzinfo=ZoneInfo('UTC')),
        has_subevents=True,
    )
    event.settings.timezone = 'Asia/Kolkata'
    for number, day in ((1, 1), (2, 8)):
        subevent = event.subevents.create(
            name=f'Session {number}', date_from=datetime(2027, 2, day, 9, 0, tzinfo=ZoneInfo('UTC')), active=True
        )
        event.quotas.create(name=f'Session {number} tickets', size=10, subevent=subevent)
        event.checkin_lists.create(name=f'Session {number} entrance', subevent=subevent)
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=organizer, can_view_orders=True, can_change_items=True, can_view_vouchers=True)
    team.members.add(user)
    team.limit_events.add(event)
    return event


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    'url_name',
    [
        'control:event.subevents.select2',
        'control:event.products.quotas.select2',
        'control:event.orders.checkinlists.select2',
        'control:event.vouchers.productselect2',
    ],
)
def test_searching_an_event_series_by_date(client, event, url_name):
    client.force_login(User.objects.get(email='dummy@dummy.dummy'))
    url = reverse(url_name, kwargs={'organizer': 'dummy', 'event': 'dummy'})

    response = client.get(url, {'query': '2027-02-01'})

    assert response.status_code == 200
    results = response.json()['results']
    assert len(results) == 1
    assert 'Session 1' in str(results[0])
    assert 'Session 2' not in str(results[0])
