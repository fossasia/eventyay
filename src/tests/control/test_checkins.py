from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Checkin,
    Event,
    Item,
    Order,
    OrderPosition,
    Organizer,
    Team,
    User,
)
from pretix.control.views.dashboards import checkin_widget
from pretix.base.services.checkin import validate_position_for_checkin_list

# --------------------------
# Fixtures for basic dashboard
# --------------------------
@pytest.fixture
def dashboard_env():
    """Create a basic event environment with organizer, event, items, and orders for dashboard testing."""
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='pretix.plugins.banktransfer,tests.testdummy',
    )
    event.settings.set('ticketoutput_testdummy__enabled', True)
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    item_ticket = Item.objects.create(event=event, name='Ticket', default_price=23, admission=True)
    item_mascot = Item.objects.create(event=event, name='Mascot', default_price=10, admission=False)

    t = Team.objects.create(organizer=o, can_view_orders=True, can_change_orders=True)
    t.members.add(user)
    t.limit_events.add(event)

    cl = event.checkin_lists.create(name='Default', all_products=True)

    event.settings.set('attendee_names_asked', True)
    event.settings.set('locales', ['en', 'de'])

    order_paid = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=33,
        locale='en',
    )
    OrderPosition.objects.create(
        order=order_paid,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Peter'},
    )
    OrderPosition.objects.create(order=order_paid, item=item_mascot, variation=None, price=Decimal('10'))

    return event, user, o, order_paid, item_ticket, item_mascot, cl


# --------------------------
# Dashboard widget tests
# --------------------------
@pytest.mark.django_db
@scopes_disabled()
def test_dashboard(dashboard_env):
    """Dashboard shows correct check-in count for paid orders with no check-ins."""
    c = checkin_widget(dashboard_env[0])
    assert '0/2' in c[0]['content']


@pytest.mark.django_db
@scopes_disabled()
def test_dashboard_pending_not_count(dashboard_env):
    """Pending orders should not be counted in dashboard check-in widget."""
    order_pending = Order.objects.create(
        code='FOO',
        event=dashboard_env[0],
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )
    OrderPosition.objects.create(
        order=order_pending,
        item=dashboard_env[4],
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'NotPaid'},
    )
    c = checkin_widget(dashboard_env[0])
    assert '0/2' in c[0]['content']


@pytest.mark.django_db
@scopes_disabled()
def test_dashboard_with_checkin(dashboard_env):
    """Dashboard count updates when check-ins are recorded."""
    op = OrderPosition.objects.get(order=dashboard_env[3], item=dashboard_env[4])
    Checkin.objects.create(position=op, list=dashboard_env[6])
    c = checkin_widget(dashboard_env[0])
    assert '1/2' in c[0]['content']


# --------------------------
# Fixtures for check-in list
# --------------------------
@pytest.fixture
def checkin_list_env():
    """Comprehensive check-in list environment with multiple orders and positions."""
    # Organizer, user, and team
    orga = Organizer.objects.create(name='Dummy', slug='dummy')
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=orga, can_view_orders=True, can_change_orders=True)
    team.members.add(user)

    # Event
    event = Event.objects.create(
        organizer=orga,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='pretix.plugins.banktransfer,tests.testdummy',
    )
    event.settings.set('ticketoutput_testdummy__enabled', True)
    event.settings.set('attendee_names_asked', True)
    event.settings.set('locales', ['en', 'de'])
    team.limit_events.add(event)

    cl = event.checkin_lists.create(name='Default', all_products=True)

    # Items
    item_ticket = Item.objects.create(event=event, name='Ticket', default_price=23, admission=True, position=0)
    item_mascot = Item.objects.create(event=event, name='Mascot', default_price=10, admission=False, position=1)

    # Orders
    order_pending = Order.objects.create(
        code='PENDING', event=event, email='dummy@dummy.test',
        status=Order.STATUS_PENDING, datetime=now(), expires=now() + timedelta(days=10), total=23, locale='en'
    )
    order_a1 = Order.objects.create(
        code='A1', event=event, email='a1dummy@dummy.test',
        status=Order.STATUS_PAID, datetime=now(), expires=now() + timedelta(days=10), total=33, locale='en'
    )
    order_a2 = Order.objects.create(
        code='A2', event=event, email='a2dummy@dummy.test',
        status=Order.STATUS_PAID, datetime=now(), expires=now() + timedelta(days=10), total=23, locale='en'
    )
    order_a3 = Order.objects.create(
        code='A3', event=event, email='a3dummy@dummy.test',
        status=Order.STATUS_PAID, datetime=now(), expires=now() + timedelta(days=10), total=23, locale='en'
    )

    # Order positions
    op_pending_ticket = OrderPosition.objects.create(order=order_pending, item=item_ticket, variation=None,
                                                     price=Decimal('23'), attendee_name_parts={'full_name': 'Pending'})
    op_a1_ticket = OrderPosition.objects.create(order=order_a1, item=item_ticket, variation=None,
                                                price=Decimal('23'), attendee_name_parts={'full_name': 'A1'})
    op_a1_mascot = OrderPosition.objects.create(order=order_a1, item=item_mascot, variation=None, price=Decimal('10'))
    op_a2_ticket = OrderPosition.objects.create(order=order_a2, item=item_ticket, variation=None,
                                                price=Decimal('23'), attendee_name_parts={'full_name': 'A2'})
    op_a3_ticket = OrderPosition.objects.create(order=order_a3, item=item_ticket, variation=None,
                                                price=Decimal('23'), attendee_name_parts={'full_name': 'a4'},
                                                attendee_email='a3company@dummy.test')

    # Pre-checkins
    Checkin.objects.create(position=op_a1_ticket, datetime=now() + timedelta(minutes=1), list=cl)
    Checkin.objects.create(position=op_a3_ticket, list=cl)

    return (
        event, user, orga, [item_ticket, item_mascot],
        [order_pending, order_a1, order_a2, order_a3],
        [op_pending_ticket, op_a1_ticket, op_a1_mascot, op_a2_ticket, op_a3_ticket],
        cl,
    )


# --------------------------
# Test manual check-ins with validation
# --------------------------
@pytest.mark.django_db
def test_manual_checkins_unauthorized_position(checkin_list_env):
    """
    Test that unauthorized positions from other events cannot be checked in.
    """
    # Position from a different event
    other_orga = Organizer.objects.create(name='Other', slug='other')
    other_event = Event.objects.create(organizer=other_orga, name='Other Event', slug='other', date_from=now())
    other_item = Item.objects.create(event=other_event, name='Other Ticket', default_price=23, admission=True)
    other_order = Order.objects.create(
        code='OTHER', event=other_event, email='other@dummy.test',
        status=Order.STATUS_PAID, datetime=now(), expires=now() + timedelta(days=10), total=23, locale='en'
    )
    other_position = OrderPosition.objects.create(
        order=other_order, item=other_item, variation=None, price=Decimal('23'),
        attendee_name_parts={'full_name': 'Other'},
    )

    # Validate manually
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(other_position, checkin_list_env[6])
        assert not is_valid
        assert "does not belong to this event" in error_msg


@pytest.mark.django_db
def test_manual_checkins_authorized_position(checkin_list_env):
    """
    Test that authorized positions can be checked in.
    """
    valid_position = checkin_list_env[5][1]  # e.g., op_a1_ticket
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(valid_position, checkin_list_env[6])
        assert is_valid
        assert error_msg == ""
