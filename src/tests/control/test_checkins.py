from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled
from freezegun import freeze_time

from pretix.base.models import (
    Checkin,
    Event,
    Item,
    ItemAddOn,
    ItemCategory,
    LogEntry,
    Order,
    OrderPosition,
    Organizer,
    Team,
    User,
)
from pretix.control.views.dashboards import checkin_widget
from pretix.base.services.checkin import validate_position_for_checkin_list

from ..base import SoupTest, extract_form_fields


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


@pytest.mark.django_db
@scopes_disabled()
def test_dashboard(dashboard_env):
    """Test that dashboard shows correct check-in count for paid orders with no check-ins."""
    c = checkin_widget(dashboard_env[0])
    assert '0/2' in c[0]['content']


@pytest.mark.django_db
@scopes_disabled()
def test_dashboard_pending_not_count(dashboard_env):
    """Test that pending orders are not counted in dashboard check-in widget."""
    # Create pending order first
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
    
    # Then check the dashboard - should still only count paid orders
    c = checkin_widget(dashboard_env[0])
    assert '0/2' in c[0]['content']


@pytest.mark.django_db
@scopes_disabled()
def test_dashboard_with_checkin(dashboard_env):
    """Test dashboard count updates when check-ins are recorded."""
    op = OrderPosition.objects.get(order=dashboard_env[3], item=dashboard_env[4])
    Checkin.objects.create(position=op, list=dashboard_env[6])
    c = checkin_widget(dashboard_env[0])
    assert '1/2' in c[0]['content']


@pytest.fixture
def checkin_list_env():
    """Create a comprehensive check-in list environment with multiple orders and positions."""
    # permission
    orga = Organizer.objects.create(name='Dummy', slug='dummy')
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=orga, can_view_orders=True, can_change_orders=True)
    team.members.add(user)

    # event
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

    # item
    item_ticket = Item.objects.create(event=event, name='Ticket', default_price=23, admission=True, position=0)
    item_mascot = Item.objects.create(event=event, name='Mascot', default_price=10, admission=False, position=1)

    # order
    order_pending = Order.objects.create(
        code='PENDING',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )
    order_a1 = Order.objects.create(
        code='A1',
        event=event,
        email='a1dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=33,
        locale='en',
    )
    order_a2 = Order.objects.create(
        code='A2',
        event=event,
        email='a2dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )
    order_a3 = Order.objects.create(
        code='A3',
        event=event,
        email='a3dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )

    # order position
    op_pending_ticket = OrderPosition.objects.create(
        order=order_pending,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Pending'},
    )
    op_a1_ticket = OrderPosition.objects.create(
        order=order_a1,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'A1'},
    )
    op_a1_mascot = OrderPosition.objects.create(order=order_a1, item=item_mascot, variation=None, price=Decimal('10'))
    op_a2_ticket = OrderPosition.objects.create(
        order=order_a2,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'A2'},
    )
    op_a3_ticket = OrderPosition.objects.create(
        order=order_a3,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'a4'},  # a3 attendee is a4 - testing name mismatch
        attendee_email='a3company@dummy.test',
    )

    # checkin
    Checkin.objects.create(position=op_a1_ticket, datetime=now() + timedelta(minutes=1), list=cl)
    Checkin.objects.create(position=op_a3_ticket, list=cl)

    return (
        event,
        user,
        orga,
        [item_ticket, item_mascot],
        [order_pending, order_a1, order_a2, order_a3],
        [op_pending_ticket, op_a1_ticket, op_a1_mascot, op_a2_ticket, op_a3_ticket],
        cl,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    'order_key, expected',
    [
        ('', ['A1Ticket', 'A1Mascot', 'A2Ticket', 'A3Ticket']),
        ('-code', ['A3Ticket', 'A2Ticket', 'A1Ticket', 'A1Mascot']),
        ('code', ['A1Mascot', 'A1Ticket', 'A2Ticket', 'A3Ticket']),
        ('-email', ['A3Ticket', 'A2Ticket', 'A1Ticket', 'A1Mascot']),
        ('email', ['A1Mascot', 'A1Ticket', 'A2Ticket', 'A3Ticket']),
        ('-status', ['A3Ticket', 'A1Ticket', 'A2Ticket', 'A1Mascot']),
        ('status', ['A1Mascot', 'A2Ticket', 'A1Ticket', 'A3Ticket']),
        (
            '-timestamp',
            ['A1Ticket', 'A3Ticket', 'A2Ticket', 'A1Mascot'],
        ),  # A1 checkin date > A3 checkin date (more recent)
        ('timestamp', ['A1Mascot', 'A2Ticket', 'A3Ticket', 'A1Ticket']),
        ('-name', ['A3Ticket', 'A2Ticket', 'A1Ticket', 'A1Mascot']),
        (
            'name',
            ['A1Mascot', 'A1Ticket', 'A2Ticket', 'A3Ticket'],
        ),  # mascot doesn't include attendee name (comes first in ascending)
        ('-item', ['A3Ticket', 'A2Ticket', 'A1Ticket', 'A1Mascot']),
        ('item', ['A1Mascot', 'A1Ticket', 'A2Ticket', 'A3Ticket']),
    ],
)
def test_checkins_list_ordering(client, checkin_list_env, order_key, expected):
    """Test that check-in list supports various ordering options including code, email, status, and timestamps."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    response = client.get(
        f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/?ordering={order_key}'
    )
    qs = response.context['entries']
    item_keys = [q.order.code + str(q.item.name) for q in qs]
    assert item_keys == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    'query, expected',
    [
        ('status=&item=&user=', ['A1Ticket', 'A1Mascot', 'A2Ticket', 'A3Ticket']),
        ('status=1&item=&user=', ['A1Ticket', 'A3Ticket']),  # status=1 means checked in
        ('status=0&item=&user=', ['A1Mascot', 'A2Ticket']),  # status=0 means not checked in
        ('status=&item=&user=a3dummy', ['A3Ticket']),  # match order email
        ('status=&item=&user=a3dummy', ['A3Ticket']),  # match order email (duplicate test case)
        ('status=&item=&user=a4', ['A3Ticket']),  # match attendee name (different from order email)
        ('status=&item=&user=a3company', ['A3Ticket']),  # match attendee email
        ('status=1&item=&user=a3company', ['A3Ticket']),  # combined status and user filter
    ],
)
def test_checkins_list_filter(client, checkin_list_env, query, expected):
    """Test that check-in list supports filtering by status and user attributes (email, attendee name)."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    response = client.get(f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/?{query}')
    qs = response.context['entries']
    item_keys = [q.order.code + str(q.item.name) for q in qs]
    assert item_keys == expected


@pytest.mark.django_db
def test_checkins_item_filter(client, checkin_list_env):
    """Test filtering check-in list by specific items - each item should only show its own positions."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    for item in checkin_list_env[3]:
        response = client.get(
            f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/?item={item.pk}'
        )
        assert all(i.item.id == item.id for i in response.context['entries'])


@pytest.mark.django_db
@pytest.mark.parametrize(
    'query, expected',
    [
        (
            'status=&item=&user=&ordering=',
            ['A1Ticket', 'A1Mascot', 'A2Ticket', 'A3Ticket'],
        ),
        ('status=1&item=&user=&ordering=timestamp', ['A3Ticket', 'A1Ticket']),  # checked-in by timestamp
        ('status=0&item=&user=&ordering=-name', ['A2Ticket', 'A1Mascot']),  # not checked-in by name desc
    ],
)
def test_checkins_list_mixed(client, checkin_list_env, query, expected):
    """Test combined filtering and ordering in check-in list - both filters and sort should work together."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    response = client.get(f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/?{query}')
    qs = response.context['entries']
    item_keys = [q.order.code + str(q.item.name) for q in qs]
    assert item_keys == expected


@pytest.mark.django_db
def test_manual_checkins(client, checkin_list_env):
    """Test manual check-in of valid positions creates check-in record and log entry."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    with scopes_disabled():
        assert not checkin_list_env[5][3].checkins.exists()
    
    # Test with valid position
    response = client.post(
        f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/',
        {'checkin': [checkin_list_env[5][3].pk]},
    )
    
    # Verify successful check-in
    assert response.status_code == 200
    with scopes_disabled():
        assert checkin_list_env[5][3].checkins.exists()
    assert LogEntry.objects.filter(
        action_type='pretix.event.checkin', object_id=checkin_list_env[5][3].order.pk
    ).exists()


@pytest.mark.django_db
def test_manual_checkins_unauthorized_position(client, checkin_list_env):
    """Test that unauthorized positions from other events cannot be checked in and show proper errors."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    
    # Create a position from a different event that shouldn't be checkable
    other_orga = Organizer.objects.create(name='Other', slug='other')
    other_event = Event.objects.create(
        organizer=other_orga,
        name='Other Event',
        slug='other',
        date_from=now(),
    )
    other_item = Item.objects.create(event=other_event, name='Other Ticket', default_price=23, admission=True)
    other_order = Order.objects.create(
        code='OTHER',
        event=other_event,
        email='other@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )
    other_position = OrderPosition.objects.create(
        order=other_order,
        item=other_item,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Other'},
    )
    
    # Try to check in the unauthorized position
    with scopes_disabled():
        is_valid, error_msg = validate_position_for_checkin_list(other_position, checkin_list_env[6])
        assert not is_valid
        initial_checkin_count = Checkin.objects.count()
        initial_log_count = LogEntry.objects.count()
    
    response = client.post(
        f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/',
        {'checkin': [other_position.pk]},
    )
    
    # Verify error response and no changes to database
    assert response.status_code == 200
    content = response.content.decode()
    assert 'alert-danger' in content or 'error' in content
    
    with scopes_disabled():
        # Check-in count should remain unchanged
        assert Checkin.objects.count() == initial_checkin_count
        assert not other_position.checkins.exists()
        
        # No log entries should be created for unauthorized operations
        assert LogEntry.objects.count() == initial_log_count
        assert not LogEntry.objects.filter(
            action_type='pretix.event.checkin',
            object_id=other_position.order.pk
        ).exists()


@pytest.mark.django_db
def test_manual_checkins_revert(client, checkin_list_env):
    """Test reverting a check-in removes the check-in record and creates proper log entries."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    with scopes_disabled():
        assert not checkin_list_env[5][3].checkins.exists()
    
    # Perform check-in then revert it
    client.post(
        f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/',
        {'checkin': [checkin_list_env[5][3].pk]},
    )
    client.post(
        f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/',
        {'checkin': [checkin_list_env[5][3].pk], 'revert': 'true'},
    )
    
    # Verify check-in was reverted and proper logs created
    with scopes_disabled():
        assert not checkin_list_env[5][3].checkins.exists()
    
    assert LogEntry.objects.filter(
        action_type='pretix.event.checkin', object_id=checkin_list_env[5][3].order.pk
    ).exists()
    assert LogEntry.objects.filter(
        action_type='pretix.event.checkin.reverted',
        object_id=checkin_list_env[5][3].order.pk,
    ).exists()


@pytest.mark.django_db
def test_manual_checkins_revert_unauthorized_position(client, checkin_list_env):
    """Test that unauthorized positions cannot be reverted even if they somehow have check-ins."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    
    # Create a position from a different event
    other_orga = Organizer.objects.create(name='Other', slug='other')
    other_event = Event.objects.create(
        organizer=other_orga,
        name='Other Event',
        slug='other',
        date_from=now(),
    )
    other_item = Item.objects.create(event=other_event, name='Other Ticket', default_price=23, admission=True)
    other_order = Order.objects.create(
        code='OTHER',
        event=other_event,
        email='other@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )
    other_position = OrderPosition.objects.create(
        order=other_order,
        item=other_item,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Other'},
    )
    
    # Create a checkin for the unauthorized position (simulating it was somehow created)
    with scopes_disabled():
        Checkin.objects.create(position=other_position, list=checkin_list_env[6])
        initial_checkin_count = Checkin.objects.count()
        initial_log_count = LogEntry.objects.count()
    
    # Try to revert the unauthorized position
    response = client.post(
        f'/control/event/dummy/dummy/checkinlists/{checkin_list_env[6].pk}/',
        {'checkin': [other_position.pk], 'revert': 'true'},
    )
    
    # Verify error response and no changes to database
    assert response.status_code == 200
    content = response.content.decode()
    assert 'alert-danger' in content or 'error' in content
    
    with scopes_disabled():
        # Check-in count should remain unchanged
        assert Checkin.objects.count() == initial_checkin_count
        assert other_position.checkins.exists()
        
        # No log entries should be created for unauthorized operations
        assert LogEntry.objects.count() == initial_log_count
        assert not LogEntry.objects.filter(
            action_type='pretix.event.checkin.reverted',
            object_id=other_position.order.pk
        ).exists()


@pytest.fixture
def checkin_list_with_addon_env():
    """Create check-in list environment with add-on items to test attendee name inheritance."""
    # permission
    orga = Organizer.objects.create(name='Dummy', slug='dummy')
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=orga, can_view_orders=True, can_change_orders=True)
    team.members.add(user)

    # event
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

    # item
    cat_adm = ItemCategory.objects.create(event=event, name='Admission')
    cat_workshop = ItemCategory.objects.create(event=event, name='Admission', is_addon=True)
    item_ticket = Item.objects.create(event=event, name='Ticket', default_price=23, admission=True, category=cat_adm)
    item_workshop = Item.objects.create(
        event=event,
        name='Workshop',
        default_price=10,
        admission=False,
        category=cat_workshop,
    )
    ItemAddOn.objects.create(base_item=item_ticket, addon_category=cat_workshop, min_count=0, max_count=2)

    # order
    order_pending = Order.objects.create(
        code='PENDING',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )
    order_a1 = Order.objects.create(
        code='A1',
        event=event,
        email='a1dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=33,
        locale='en',
    )
    order_a2 = Order.objects.create(
        code='A2',
        event=event,
        email='a2dummy@dummy.test',
        status=Order.STATUS_PAID,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=23,
        locale='en',
    )

    # order position
    op_pending_ticket = OrderPosition.objects.create(
        order=order_pending,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'Pending'},
    )
    op_a1_ticket = OrderPosition.objects.create(
        order=order_a1,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'A1'},
    )
    op_a1_workshop = OrderPosition.objects.create(
        order=order_a1,
        item=item_workshop,
        variation=None,
        price=Decimal('10'),
        addon_to=op_a1_ticket,
    )
    op_a2_ticket = OrderPosition.objects.create(
        order=order_a2,
        item=item_ticket,
        variation=None,
        price=Decimal('23'),
        attendee_name_parts={'full_name': 'A2'},
    )

    # checkin
    Checkin.objects.create(position=op_a1_ticket, datetime=now() + timedelta(minutes=1), list=cl)

    return (
        event,
        user,
        orga,
        [item_ticket, item_workshop],
        [order_pending, order_a1, order_a2],
        [op_pending_ticket, op_a1_ticket, op_a1_workshop, op_a2_ticket],
        cl,
    )


@pytest.mark.django_db
def test_checkins_attendee_name_from_addon_available(client, checkin_list_with_addon_env):
    """Test that add-on positions inherit attendee names from their parent positions in check-in list."""
    client.login(email='dummy@dummy.dummy', password='dummy')
    response = client.get(f'/control/event/dummy/dummy/checkinlists/{checkin_list_with_addon_env[6].pk}/')
    qs = response.context['entries']
    item_keys = [
        q.order.code
        + str(q.item.name)
        + (str(q.addon_to.attendee_name) if q.addon_to is not None else str(q.attendee_name))
        for q in qs
    ]
    assert item_keys == [
        'A1TicketA1',
        'A1WorkshopA1',  # A1Workshop inherits name from A1Ticket (addon_to relationship)
        'A2TicketA2',
    ]


class CheckinListFormTest(SoupTest):
    """Test check-in list creation, update, and deletion forms."""
    
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        self.orga1 = Organizer.objects.create(name='CCC', slug='ccc')
        self.event1 = Event.objects.create(
            organizer=self.orga1,
            name='30C3',
            slug='30c3',
            date_from=datetime(2013, 12, 26, tzinfo=timezone.utc),
        )
        self.event1.settings.timezone = 'Europe/Berlin'
        t = Team.objects.create(organizer=self.orga1, can_change_event_settings=True, can_view_orders=True)
        t.members.add(self.user)
        t.limit_events.add(self.event1)
        self.client.login(email='dummy@dummy.dummy', password='dummy')
        self.item_ticket = Item.objects.create(event=self.event1, name='Ticket', default_price=23, admission=True)

    def test_create(self):
        """Test creating a new check-in list with all products enabled."""
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/add')
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['name'] = 'All'
        form_data['all_products'] = 'on'
        doc = self.post_doc(
            f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/add',
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertIn('All', doc.select('#page-wrapper table')[0].text)
        with scopes_disabled():
            assert self.event1.checkin_lists.get(name='All', all_products=True)

    def test_update(self):
        """Test updating an existing check-in list to limit products."""
        with scopes_disabled():
            cl = self.event1.checkin_lists.create(name='All', all_products=True)
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/change')
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['all_products'] = ''
        form_data['limit_products'] = str(self.item_ticket.pk)
        doc = self.post_doc(
            f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/change',
            form_data,
        )
        assert doc.select('.alert-success')
        cl.refresh_from_db()
        assert not cl.all_products
        with scopes_disabled():
            assert list(cl.limit_products.all()) == [self.item_ticket]

    @freeze_time('2020-01-02 02:55:00+01:00')
    def test_update_exit_all_at_current_day(self):
        """Test setting exit_all_at time for current day in Europe/Berlin timezone."""
        with scopes_disabled():
            cl = self.event1.checkin_lists.create(name='All', all_products=True)
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/change')
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['exit_all_at'] = '03:00:00'
        doc = self.post_doc(
            f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/change',
            form_data,
        )
        assert doc.select('.alert-success')
        cl.refresh_from_db()
        # 03:00:00 in Europe/Berlin (UTC+1) should be 02:00:00 UTC
        assert cl.exit_all_at == datetime(2020, 1, 2, 2, 0, 0, tzinfo=timezone.utc)

    @freeze_time('2020-01-02 03:05:00+01:00')
    def test_update_exit_all_at_next_day(self):
        """Test setting exit_all_at time when current time is after the target time (next day logic)."""
        with scopes_disabled():
            cl = self.event1.checkin_lists.create(name='All', all_products=True)
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/change')
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        form_data['exit_all_at'] = '03:00:00'
        doc = self.post_doc(
            f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/change',
            form_data,
        )
        assert doc.select('.alert-success')
        cl.refresh_from_db()
        # 03:00:00 in Europe/Berlin (UTC+1) should be 02:00:00 UTC
        assert cl.exit_all_at == datetime(2020, 1, 2, 2, 0, 0, tzinfo=timezone.utc)

    def test_delete(self):
        """Test deleting a check-in list removes it from the database."""
        with scopes_disabled():
            cl = self.event1.checkin_lists.create(name='All', all_products=True)
        doc = self.get_doc(f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/delete')
        form_data = extract_form_fields(doc.select('.container-fluid form')[0])
        doc = self.post_doc(
            f'/control/event/{self.orga1.slug}/{self.event1.slug}/checkinlists/{cl.id}/delete',
            form_data,
        )
        assert doc.select('.alert-success')
        self.assertNotIn('VAT', doc.select('#page-wrapper')[0].text)
        with scopes_disabled():
            assert not self.event1.checkin_lists.exists()