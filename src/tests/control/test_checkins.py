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
    OrderPosition.objects.create(
        order=order_paid,
        item=item_mascot,
        variation=None,
        price=Decimal('10')
    )

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
    event = dashboard_env[0]
    item_ticket = dashboard_env[4]
    
    order_pending = Order.objects.create(
        code='BAR',
        event=event,
        email='pending@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )
    OrderPosition.objects.create(
        order=order_pending,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'NotPaid'},
    )
    
    c = checkin_widget(event)
    assert '0/2' in c[0]['content']


@pytest.mark.django_db
@scopes_disabled()
def test_dashboard_with_checkin(dashboard_env):
    """Dashboard count updates when check-ins are recorded."""
    event, user, o, order_paid, item_ticket, item_mascot, cl = dashboard_env
    
    op = OrderPosition.objects.get(order=order_paid, item=item_ticket)
    Checkin.objects.create(position=op, list=cl)
    
    c = checkin_widget(event)
    assert '1/2' in c[0]['content']


# --------------------------
# Check-in for non-admission item (Mascot)
# --------------------------
@pytest.mark.django_db
@scopes_disabled()
def test_dashboard_non_admission_item_checkin(dashboard_env):
    """Dashboard should not count check-ins for non-admission items."""
    event, user, o, order_paid, item_ticket, item_mascot, cl = dashboard_env
    
    # Check in the non-admission item (Mascot)
    op_mascot = OrderPosition.objects.get(order=order_paid, item=item_mascot)
    Checkin.objects.create(position=op_mascot, list=cl)
    
    # Dashboard should show 0/2 because mascot is not an admission item
    c = checkin_widget(event)
    assert '0/2' in c[0]['content']


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
    item_ticket = Item.objects.create(
        event=event,
        name='Ticket',
        default_price=23,
        admission=True,
        position=0
    )
    item_mascot = Item.objects.create(
        event=event,
        name='Mascot',
        default_price=10,
        admission=False,
        position=1
    )

    # Orders
    order_pending = Order.objects.create(
        code='PENDING',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en'
    )
    
    order_a1 = Order.objects.create(
        code='A1',
        event=event,
        email='a1dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=33,
        locale='en'
    )
    
    order_a2 = Order.objects.create(
        code='A2',
        event=event,
        email='a2dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en'
    )
    
    order_a3 = Order.objects.create(
        code='A3',
        event=event,
        email='a3dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en'
    )
    
    # Expired order
    order_expired = Order.objects.create(
        code='EXPIRED',
        event=event,
        email='expired@dummy.test',
        status=Order.STATUS_EXPIRED,
        datetime=now(),
        expires=now() - timedelta(days=1),
        total=23,
        locale='en'
    )
    
    # Canceled order
    order_canceled = Order.objects.create(
        code='CANCELED',
        event=event,
        email='canceled@dummy.test',
        status=Order.STATUS_CANCELED,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en'
    )

    # Order positions
    op_pending_ticket = OrderPosition.objects.create(
        order=order_pending,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Pending'}
    )
    
    op_a1_ticket = OrderPosition.objects.create(
        order=order_a1,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'A1'}
    )
    
    op_a1_mascot = OrderPosition.objects.create(
        order=order_a1,
        item=item_mascot,
        variation=None,
        price=Decimal('10')
    )
    
    op_a2_ticket = OrderPosition.objects.create(
        order=order_a2,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'A2'}
    )
    
    op_a3_ticket = OrderPosition.objects.create(
        order=order_a3,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'a4'},
        attendee_email='a3company@dummy.test'
    )
    
    # Position for expired order
    op_expired_ticket = OrderPosition.objects.create(
        order=order_expired,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Expired'}
    )
    
    # Position for canceled order
    op_canceled_ticket = OrderPosition.objects.create(
        order=order_canceled,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Canceled'}
    )

    # Pre-checkins
    Checkin.objects.create(
        position=op_a1_ticket,
        datetime=now() + timedelta(minutes=1),
        list=cl
    )
    Checkin.objects.create(position=op_a3_ticket, list=cl)

    return {
        'event': event,
        'user': user,
        'organizer': orga,
        'items': [item_ticket, item_mascot],
        'orders': [order_pending, order_a1, order_a2, order_a3, order_expired, order_canceled],
        'positions': [op_pending_ticket, op_a1_ticket, op_a1_mascot, op_a2_ticket, op_a3_ticket, 
                      op_expired_ticket, op_canceled_ticket],
        'checkin_list': cl,
    }


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
    other_event = Event.objects.create(
        organizer=other_orga,
        name='Other Event',
        slug='other',
        date_from=now()
    )
    other_item = Item.objects.create(
        event=other_event,
        name='Other Ticket',
        default_price=23,
        admission=True
    )
    other_order = Order.objects.create(
        code='OTHER',
        event=other_event,
        email='other@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en'
    )
    other_position = OrderPosition.objects.create(
        order=other_order,
        item=other_item,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Other'},
    )

    # Validate manually
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(
            other_position,
            checkin_list_env['checkin_list']
        )
        assert not is_valid
        assert "does not belong to this event" in error_msg


@pytest.mark.django_db
def test_manual_checkins_authorized_position(checkin_list_env):
    """
    Test that authorized positions can be checked in.
    """
    valid_position = checkin_list_env['positions'][1]  # op_a1_ticket
    
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(
            valid_position,
            checkin_list_env['checkin_list']
        )
        assert is_valid
        assert error_msg == ""


# --------------------------
# Duplicate check-in attempt
# --------------------------
@pytest.mark.django_db
def test_manual_checkins_duplicate_checkin(checkin_list_env):
    """
    Test that duplicate check-ins are allowed by default (re-entry).
    """
    already_checked_in_position = checkin_list_env['positions'][1]  # op_a1_ticket (already has a checkin)
    
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(
            already_checked_in_position,
            checkin_list_env['checkin_list']
        )
        # Pretix allows re-entry by default
        assert is_valid is True
        assert error_msg == ""


# --------------------------
# Expired order status behaviour
# --------------------------
@pytest.mark.django_db
def test_manual_checkins_expired_order(checkin_list_env):
    """
    Test that positions from expired orders should be denied check-in.
    """
    expired_position = checkin_list_env['positions'][5]  # op_expired_ticket
    
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(
            expired_position,
            checkin_list_env['checkin_list']
        )
        assert not is_valid
        assert any(term in error_msg.lower() for term in ['expired', 'invalid', 'not paid', 'status'])


# --------------------------
# Canceled / refunded order
# --------------------------
@pytest.mark.django_db
def test_manual_checkins_canceled_order(checkin_list_env):
    """
    Test that positions from canceled orders should be rejected.
    """
    canceled_position = checkin_list_env['positions'][6]  # op_canceled_ticket
    
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(
            canceled_position,
            checkin_list_env['checkin_list']
        )
        assert not is_valid
        assert any(term in error_msg.lower() for term in ['canceled', 'cancelled', 'refunded', 'invalid', 'status'])


# --------------------------
# Pending order check-in attempt
# --------------------------
@pytest.mark.django_db
def test_manual_checkins_pending_order(checkin_list_env):
    """
    Test that positions from pending orders should be denied check-in.
    """
    pending_position = checkin_list_env['positions'][0]  # op_pending_ticket
    
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(
            pending_position,
            checkin_list_env['checkin_list']
        )
        assert not is_valid
        assert any(term in error_msg.lower() for term in ['pending', 'not paid', 'unpaid', 'status'])


# --------------------------
# Non-admission item check-in validation
# --------------------------
@pytest.mark.django_db
def test_manual_checkins_non_admission_item(checkin_list_env):
    """
    Test that non-admission items can be checked in when checkin_list.all_products=True.
    """
    non_admission_position = checkin_list_env['positions'][2]  # op_a1_mascot (non-admission item)
    
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(
            non_admission_position,
            checkin_list_env['checkin_list']
        )
        # With checkin_list.all_products=True, even non-admission items should be valid
        assert is_valid is True
        assert error_msg == ""


# --------------------------
# Check-in list with restricted products
# --------------------------
@pytest.mark.django_db
def test_checkin_list_restricted_products():
    """
    Test check-in validation with a check-in list that only includes specific products.
    """
    # Setup
    orga = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=orga,
        name='Dummy',
        slug='dummy',
        date_from=now(),
    )
    
    # Create multiple items
    item_vip = Item.objects.create(event=event, name='VIP Ticket', default_price=50, admission=True)
    item_regular = Item.objects.create(event=event, name='Regular Ticket', default_price=23, admission=True)
    item_workshop = Item.objects.create(event=event, name='Workshop', default_price=30, admission=False)
    
    # Create a check-in list that only includes VIP tickets
    cl_vip_only = event.checkin_lists.create(name='VIP Only', all_products=False)
    cl_vip_only.limit_products.add(item_vip)
    
    # Create a paid order with multiple positions
    order = Order.objects.create(
        code='MULTI',
        event=event,
        email='multi@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=103,
        locale='en'
    )
    
    op_vip = OrderPosition.objects.create(
        order=order,
        item=item_vip,
        price=Decimal('50'),
        attendee_name_parts={'full_name': 'VIP Guest'}
    )
    
    op_regular = OrderPosition.objects.create(
        order=order,
        item=item_regular,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Regular Guest'}
    )
    
    op_workshop = OrderPosition.objects.create(
        order=order,
        item=item_workshop,
        price=Decimal('30')
    )
    
    # Test validation
    with scopes_disabled():
        # VIP ticket should be valid for VIP-only check-in list
        is_valid_vip, error_vip = validate_position_for_checkin_list(op_vip, cl_vip_only)
        assert is_valid_vip
        assert error_vip == ""
        
        # Regular ticket should NOT be valid for VIP-only check-in list
        is_valid_regular, error_regular = validate_position_for_checkin_list(op_regular, cl_vip_only)
        assert not is_valid_regular
        assert "product" in error_regular.lower() or "item" in error_regular.lower() or "list" in error_regular.lower()
        
        # Workshop (non-admission) should also NOT be valid
        is_valid_workshop, error_workshop = validate_position_for_checkin_list(op_workshop, cl_vip_only)
        assert not is_valid_workshop
        assert "product" in error_workshop.lower() or "item" in error_workshop.lower() or "list" in error_workshop.lower()


# --------------------------
# Check-in list with re-entry disabled
# --------------------------
@pytest.mark.django_db
def test_checkin_list_reentry_disabled():
    """
    Test check-in validation when re-entry is disabled on the check-in list.
    """
    # Setup
    orga = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=orga,
        name='Dummy',
        slug='dummy',
        date_from=now(),
    )
    
    item = Item.objects.create(event=event, name='Ticket', default_price=23, admission=True)
    
    # Create a check-in list with re-entry disabled
    cl_no_reentry = event.checkin_lists.create(
        name='No Re-entry',
        all_products=True,
        allow_multiple_entries=False  # Disable re-entry
    )
    
    # Create a paid order
    order = Order.objects.create(
        code='NORENTRY',
        event=event,
        email='test@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en'
    )
    
    op = OrderPosition.objects.create(
        order=order,
        item=item,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Test Guest'}
    )
    
    # Create initial check-in
    Checkin.objects.create(position=op, list=cl_no_reentry)
    
    # Test duplicate check-in with re-entry disabled
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(op, cl_no_reentry)
        assert not is_valid
        assert "already" in error_msg.lower() or "multiple" in error_msg.lower() or "re-entry" in error_msg.lower()


# --------------------------
# Test for check-in list that includes both admission and non-admission items
# --------------------------
@pytest.mark.django_db
def test_checkin_list_mixed_items():
    """
    Test check-in list that specifically includes both admission and non-admission items.
    """
    # Setup
    orga = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=orga,
        name='Dummy',
        slug='dummy',
        date_from=now(),
    )
    
    item_ticket = Item.objects.create(event=event, name='Ticket', default_price=23, admission=True)
    item_mascot = Item.objects.create(event=event, name='Mascot', default_price=10, admission=False)
    item_other = Item.objects.create(event=event, name='Other Item', default_price=15, admission=True)
    
    # Create check-in list that includes only ticket and mascot
    cl_mixed = event.checkin_lists.create(name='Mixed Items', all_products=False)
    cl_mixed.limit_products.add(item_ticket)
    cl_mixed.limit_products.add(item_mascot)
    
    # Create a paid order
    order = Order.objects.create(
        code='MIXED',
        event=event,
        email='mixed@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=48,
        locale='en'
    )
    
    op_ticket = OrderPosition.objects.create(
        order=order,
        item=item_ticket,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Ticket Holder'}
    )
    
    op_mascot = OrderPosition.objects.create(
        order=order,
        item=item_mascot,
        price=Decimal('10')
    )
    
    op_other = OrderPosition.objects.create(
        order=order,
        item=item_other,
        price=Decimal('15'),
        attendee_name_parts={'full_name': 'Other Holder'}
    )
    
    # Test validation
    with scopes_disabled():
        # Ticket should be valid (admission item in list)
        is_valid_ticket, error_ticket = validate_position_for_checkin_list(op_ticket, cl_mixed)
        assert is_valid_ticket
        assert error_ticket == ""
        
        # Mascot should be valid (non-admission item in list)
        is_valid_mascot, error_mascot = validate_position_for_checkin_list(op_mascot, cl_mixed)
        assert is_valid_mascot
        assert error_mascot == ""
        
        # Other item should NOT be valid (not in list)
        is_valid_other, error_other = validate_position_for_checkin_list(op_other, cl_mixed)
        assert not is_valid_other
        assert "product" in error_other.lower() or "item" in error_other.lower() or "list" in error_other.lower()