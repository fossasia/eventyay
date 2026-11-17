"""Tests for the voucher list CSV export functionality in the control area."""

import csv
import io
from urllib.parse import quote_plus

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Organizer, Product, SubEvent, Team, User
from eventyay.multidomain.models import KnownDomain


@pytest.fixture
def event():
    """Create a sample event for voucher testing."""
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Test Organizer', slug='test-org')
        event = Event.objects.create(
            organizer=organizer,
            name='Test Event',
            slug='test-event',
            date_from=now(),
        )
        event.settings.set('timezone', 'UTC')
        return event


@pytest.fixture
def ticket(event):
    """Create a sample product ticket."""
    with scope(event=event, organizer=event.organizer):
        return Product.objects.create(event=event, name='General Admission', default_price=50, admission=True)


@pytest.fixture
def control_user(event):
    """Create an organizer team user with permission to view vouchers."""
    with scopes_disabled():
        user = User.objects.create_user('voucheradmin@example.com', 'adminpass123')
        team = Team.objects.create(organizer=event.organizer, can_view_vouchers=True, can_change_vouchers=True)
        team.members.add(user)
        team.limit_events.add(event)
        return user


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_voucher_csv_download_includes_direct_link(client, event, ticket, control_user):
    """Verify that the exported CSV includes the Voucher link column and correct redeem URL."""
    with scope(event=event, organizer=event.organizer):
        event.vouchers.create(product=ticket, code='PROMO2026', tag='early')

    client.force_login(control_user)
    url = reverse('control:event.vouchers', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = client.get(f'{url}?download=yes')
    assert response.status_code == 200
    assert response['Content-Type'] == 'text/csv'
    assert 'attachment; filename="vouchers.csv"' in response['Content-Disposition']

    reader = csv.reader(io.StringIO(response.content.decode('utf-8')))
    rows = list(reader)
    headers = rows[0]

    assert headers[0] == 'Voucher code'
    assert headers[1] == 'Voucher link'

    data_row = rows[1]
    assert data_row[0] == 'PROMO2026'
    assert data_row[1] == 'https://testserver/test-org/test-event/redeem/?voucher=PROMO2026'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_voucher_csv_download_with_subevent_link(client, event, ticket, control_user):
    """Verify that vouchers tied to a subevent date include &subevent=<id> in the exported link."""
    with scopes_disabled():
        event.has_subevents = True
        event.save()
    with scope(event=event, organizer=event.organizer):
        subevent = SubEvent.objects.create(
            event=event,
            name='Day 1',
            date_from=now(),
            active=True,
        )
        event.vouchers.create(product=ticket, code='DAY1PASS', subevent=subevent)

    client.force_login(control_user)
    url = reverse('control:event.vouchers', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = client.get(f'{url}?download=yes')
    assert response.status_code == 200

    reader = csv.reader(io.StringIO(response.content.decode('utf-8')))
    rows = list(reader)
    data_row = rows[1]
    assert data_row[0] == 'DAY1PASS'
    assert data_row[1] == f'https://testserver/test-org/test-event/redeem/?voucher=DAY1PASS&subevent={subevent.pk}'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_voucher_csv_download_encodes_special_characters_in_code(client, event, ticket, control_user):
    """Verify that special characters in voucher codes are properly URL-encoded in the exported link."""
    special_code = 'SPECIAL CODE & MORE'
    with scope(event=event, organizer=event.organizer):
        event.vouchers.create(product=ticket, code=special_code)

    client.force_login(control_user)
    url = reverse('control:event.vouchers', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = client.get(f'{url}?download=yes')
    assert response.status_code == 200

    reader = csv.reader(io.StringIO(response.content.decode('utf-8')))
    rows = list(reader)
    data_row = rows[1]
    assert data_row[0] == special_code
    expected_encoded = quote_plus(special_code)
    assert data_row[1] == f'https://testserver/test-org/test-event/redeem/?voucher={expected_encoded}'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_voucher_csv_download_uses_custom_domain(client, event, ticket, control_user):
    """Verify that an event with a custom domain uses the custom domain in the voucher link."""
    with scopes_disabled():
        KnownDomain.objects.create(event=event, domainname='tickets.customdomain.org')

    with scope(event=event, organizer=event.organizer):
        event.vouchers.create(product=ticket, code='CUSTOMDOMAIN')

    client.force_login(control_user)
    url = reverse('control:event.vouchers', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = client.get(f'{url}?download=yes')
    assert response.status_code == 200

    reader = csv.reader(io.StringIO(response.content.decode('utf-8')))
    rows = list(reader)
    data_row = rows[1]
    assert data_row[0] == 'CUSTOMDOMAIN'
    assert data_row[1] == 'https://tickets.customdomain.org/redeem/?voucher=CUSTOMDOMAIN'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_voucher_csv_download_ignores_foreign_subevent(client, event, ticket, control_user):
    """Verify that vouchers referencing a subevent of a different event do not include the subevent parameter."""
    with scopes_disabled():
        other_event = Event.objects.create(
            organizer=event.organizer,
            name='Other Event',
            slug='other-event',
            date_from=now(),
            has_subevents=True,
        )
    with scope(event=other_event, organizer=other_event.organizer):
        foreign_subevent = SubEvent.objects.create(
            event=other_event,
            name='Foreign Day',
            date_from=now(),
            active=True,
        )

    with scope(event=event, organizer=event.organizer):
        event.vouchers.create(product=ticket, code='FOREIGNSE', subevent=foreign_subevent)

    client.force_login(control_user)
    url = reverse('control:event.vouchers', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = client.get(f'{url}?download=yes')
    assert response.status_code == 200

    reader = csv.reader(io.StringIO(response.content.decode('utf-8')))
    rows = list(reader)
    data_row = rows[1]
    assert data_row[0] == 'FOREIGNSE'
    assert data_row[1] == 'https://testserver/test-org/test-event/redeem/?voucher=FOREIGNSE'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_voucher_csv_download_ignores_inactive_subevent(client, event, ticket, control_user):
    """Verify that vouchers referencing an inactive subevent do not include the subevent parameter."""
    with scopes_disabled():
        event.has_subevents = True
        event.save()
    with scope(event=event, organizer=event.organizer):
        inactive_subevent = SubEvent.objects.create(
            event=event,
            name='Inactive Day',
            date_from=now(),
            active=False,
        )
        event.vouchers.create(product=ticket, code='INACTIVEDAY', subevent=inactive_subevent)

    client.force_login(control_user)
    url = reverse('control:event.vouchers', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = client.get(f'{url}?download=yes')
    assert response.status_code == 200

    reader = csv.reader(io.StringIO(response.content.decode('utf-8')))
    rows = list(reader)
    data_row = rows[1]
    assert data_row[0] == 'INACTIVEDAY'
    assert data_row[1] == 'https://testserver/test-org/test-event/redeem/?voucher=INACTIVEDAY'

