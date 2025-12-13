"""
Test fixtures for API tests.

These fixtures provide common test data for testing the API endpoints.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.test import utils
from django_scopes import scopes_disabled
from rest_framework.test import APIClient

from eventyay.base.models import (
    Device,
    Event,
    Order,
    OrderFee,
    OrderPayment,
    OrderPosition,
    Organizer,
    Team,
    User,
)
from eventyay.base.models.devices import generate_api_token


@pytest.fixture
def client():
    """Return an API test client."""
    return APIClient()


@pytest.fixture
@scopes_disabled()
def organizer():
    """Create a test organizer."""
    return Organizer.objects.create(name='Test Organizer', slug='test-organizer')


@pytest.fixture
@scopes_disabled()
def event(organizer):
    """Create a test event."""
    e = Event.objects.create(
        organizer=organizer,
        name='Test Event',
        slug='test-event',
        date_from=datetime(2025, 12, 27, 10, 0, 0, tzinfo=timezone.utc),
        plugins='eventyay.plugins.banktransfer,eventyay.plugins.ticketoutputpdf',
        is_public=True,
    )
    e.settings.timezone = 'UTC'
    return e


@pytest.fixture
@scopes_disabled()
def team(organizer):
    """Create a test team with full permissions."""
    return Team.objects.create(
        organizer=organizer,
        name='Test Team',
        can_change_teams=True,
        can_manage_gift_cards=True,
        can_change_items=True,
        can_create_events=True,
        can_change_event_settings=True,
        can_change_vouchers=True,
        can_view_vouchers=True,
        can_change_orders=True,
        can_change_organizer_settings=True,
    )


@pytest.fixture
@scopes_disabled()
def device(organizer):
    """Create a test API device."""
    return Device.objects.create(
        organizer=organizer,
        all_events=True,
        name='Test Device',
        initialized=datetime.now(timezone.utc),
        api_token=generate_api_token(),
    )


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user('test@test.test', 'testpassword')


@pytest.fixture
@scopes_disabled()
def user_client(client, team, user):
    """Return an API client authenticated as a user."""
    team.can_view_orders = True
    team.can_view_vouchers = True
    team.all_events = True
    team.save()
    team.members.add(user)
    client.force_authenticate(user=user)
    return client


@pytest.fixture
@scopes_disabled()
def token_client(client, team):
    """Return an API client authenticated with a team token."""
    team.can_view_orders = True
    team.can_view_vouchers = True
    team.all_events = True
    team.save()
    t = team.tokens.create(name='Test Token')
    client.credentials(HTTP_AUTHORIZATION='Token ' + t.token)
    return client


@pytest.fixture
def device_client(client, device):
    """Return an API client authenticated as a device."""
    client.credentials(HTTP_AUTHORIZATION='Device ' + device.api_token)
    return client


@pytest.fixture
@scopes_disabled()
def item(event):
    """Create a test product/item."""
    return event.products.create(name='Test Ticket', default_price=Decimal('100.00'))


@pytest.fixture
@scopes_disabled()
def taxrule(event):
    """Create a test tax rule."""
    return event.tax_rules.create(name='VAT', rate=Decimal('19.00'))


@pytest.fixture
@scopes_disabled()
def order(event, item, taxrule):
    """Create a test order with a payment."""
    o = Order.objects.create(
        code='TEST01',
        event=event,
        email='customer@test.test',
        status=Order.STATUS_PENDING,
        secret='testsecretkey12345',
        datetime=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        expires=datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
        total=Decimal('100.00'),
        locale='en',
    )
    
    # Create a confirmed payment
    o.payments.create(
        provider='manual',
        state=OrderPayment.PAYMENT_STATE_CONFIRMED,
        amount=Decimal('100.00'),
        payment_date=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    
    # Create a fee
    o.fees.create(
        fee_type=OrderFee.FEE_TYPE_PAYMENT,
        value=Decimal('0.00'),
        tax_rate=Decimal('0.00'),
        tax_value=Decimal('0.00'),
    )
    
    # Create an order position
    OrderPosition.objects.create(
        order=o,
        product=item,
        variation=None,
        price=Decimal('100.00'),
        attendee_name_parts={'full_name': 'Test Customer', '_scheme': 'full'},
        secret='testpositionsecret123',
        pseudonymization_id='TESTPSEUDO',
    )
    
    return o


# Apply scopes_disabled to database setup
utils.setup_databases = scopes_disabled()(utils.setup_databases)
