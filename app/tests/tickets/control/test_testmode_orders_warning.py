from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Order, Organizer, Team, User


ORDER_PAGE = '/control/event/dummy/dummy/orders/FOO/'
EVENT_STATUS_PAGE = '/common/event/dummy/dummy/live/'


@pytest.fixture
def event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=organizer, name='Dummy', slug='dummy', date_from=now() + timedelta(days=30)
        )
        user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        team = Team.objects.create(organizer=organizer, can_view_orders=True, can_change_event_settings=True)
        team.members.add(user)
        team.limit_events.add(event)
    with scope(organizer=organizer):
        Order.objects.create(
            code='FOO',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + timedelta(days=2),
            total=Decimal('0.00'),
            testmode=True,
        )
    return event


def set_ticketing_mode(event, mode):
    with scopes_disabled():
        event.testmode = mode == 'public_test'
        event.private_testmode = mode == 'private_test'
        event.save()
        event.settings.private_testmode_tickets = mode == 'private_test'
        event.cache.clear()


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize('page', [ORDER_PAGE, EVENT_STATUS_PAGE])
@pytest.mark.parametrize(
    ('mode', 'warning_shown'),
    [
        ('private_test', False),
        ('public_test', False),
        ('public_sales', True),
    ],
)
def test_testmode_orders_warning_follows_ticketing_mode(client, event, page, mode, warning_shown):
    set_ticketing_mode(event, mode)
    client.force_login(User.objects.get(email='dummy@dummy.dummy'))

    response = client.get(page)

    assert response.status_code == 200
    assert response.context['complain_testmode_orders'] is warning_shown
