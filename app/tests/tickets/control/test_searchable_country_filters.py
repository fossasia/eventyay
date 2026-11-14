import re

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, InvoiceAddress, Order, OrderPosition, Organizer, Product, Team, User
from eventyay.control.forms.filter import EventOrderExpertFilterForm


@pytest.fixture
def env():
    """Set up test environment with an event, organizer, team, and country-filtered orders."""
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Country Dummy', slug='country-dummy')
        event = Event.objects.create(
            organizer=organizer,
            name='Country Dummy Event',
            slug='country-dummy-event',
            date_from=now(),
        )
        user = User.objects.create_user('country_orga@example.com', 'dummy')
        team = Team.objects.create(
            organizer=organizer,
            can_view_orders=True,
            can_change_orders=True,
            can_change_items=True,
            all_events=True,
        )
        team.members.add(user)

    with scope(organizer=organizer, event=event):
        product = Product.objects.create(event=event, name='Standard ticket', default_price=10, admission=True)

        # Order 1: Germany (DE)
        order_de = Order.objects.create(
            event=event,
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now(),
            total=10,
            code='DE001',
            email='de_attendee@example.com',
        )
        InvoiceAddress.objects.create(order=order_de, country='DE', street='Musterstr. 1', city='Berlin')
        OrderPosition.objects.create(
            order=order_de,
            product=product,
            price=10,
            attendee_name_cached='Max Mustermann',
            country='DE',
        )

        # Order 2: Invoice in United States (US), Attendee in France (FR)
        order_us = Order.objects.create(
            event=event,
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now(),
            total=10,
            code='US001',
            email='us_attendee@example.com',
        )
        InvoiceAddress.objects.create(order=order_us, country='US', street='123 Main St', city='New York')
        OrderPosition.objects.create(
            order=order_us,
            product=product,
            price=10,
            attendee_name_cached='John Doe',
            country='FR',
        )

    return {
        'organizer': organizer,
        'event': event,
        'user': user,
        'order_de': order_de,
        'order_us': order_us,
    }


def make_url(env, name, **extra):
    """Generate a reverse URL scoped to the test organizer and event."""
    kwargs = {'organizer': env['organizer'].slug, 'event': env['event'].slug, **extra}
    return reverse(name, kwargs=kwargs)


def extract_select(content, field):
    """Extract the HTML <select> tag block for the given form field name."""
    match = re.search(rf'<select[^>]*name="{field}"[^>]*>(.*?)</select>', content, re.S)
    assert match, f'no <select name="{field}">'
    return match.group(0)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_order_search_country_filters_are_searchable(client, env):
    """Verify invoice and attendee address country dropdowns render as searchable selects on order search."""
    client.force_login(env['user'])
    url = make_url(env, 'control:event.orders.search')
    response = client.get(url)
    assert response.status_code == 200

    content = response.content.decode()

    # Verify searchable select assets are loaded
    assert 'common/js/searchable-select.js' in content
    assert 'common/css/searchable-select.css' in content

    # Check invoice_address_country filter
    invoice_select = extract_select(content, 'expert-invoice_address_country')
    invoice_tag = invoice_select.split('>', 1)[0]
    assert 'data-searchable-select' in invoice_tag
    assert 'data-all-label="All countries"' in invoice_tag
    assert 'data-search-placeholder="Search"' in invoice_tag
    assert 'data-empty-text="No results"' in invoice_tag
    assert 'All countries' in invoice_select
    assert 'Germany' in invoice_select
    assert 'United States' in invoice_select

    # Check attendee_address_country filter
    attendee_select = extract_select(content, 'expert-attendee_address_country')
    attendee_tag = attendee_select.split('>', 1)[0]
    assert 'data-searchable-select' in attendee_tag
    assert 'data-all-label="All countries"' in attendee_tag
    assert 'data-search-placeholder="Search"' in attendee_tag
    assert 'data-empty-text="No results"' in attendee_tag
    assert 'All countries' in attendee_select
    assert 'Germany' in attendee_select
    assert 'United States' in attendee_select


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_order_search_filtering_by_country(client, env):
    """Verify filtering orders by invoice and attendee address country via GET params."""
    client.force_login(env['user'])
    orders_url = make_url(env, 'control:event.orders')

    # 1. Base list without country filter shows both orders
    res_base = client.get(orders_url)
    assert res_base.status_code == 200
    assert 'DE001' in res_base.content.decode()
    assert 'US001' in res_base.content.decode()

    # 2. Filter by invoice address country: Germany (DE)
    res_de = client.get(orders_url, {'expert-invoice_address_country': 'DE'})
    assert res_de.status_code == 200
    content_de = res_de.content.decode()
    assert 'DE001' in content_de
    assert 'US001' not in content_de

    # 3. Filter by invoice address country: United States (US)
    res_invoice_us = client.get(orders_url, {'expert-invoice_address_country': 'US'})
    assert res_invoice_us.status_code == 200
    content_invoice_us = res_invoice_us.content.decode()
    assert 'US001' in content_invoice_us
    assert 'DE001' not in content_invoice_us

    # 4. Filter by attendee address country: France (FR) - matches Order 2 whose attendee is in FR
    res_attendee_fr = client.get(orders_url, {'expert-attendee_address_country': 'FR'})
    assert res_attendee_fr.status_code == 200
    content_attendee_fr = res_attendee_fr.content.decode()
    assert 'US001' in content_attendee_fr
    assert 'DE001' not in content_attendee_fr

    # 5. Filter by attendee address country: United States (US) - neither order has an attendee in US
    res_attendee_us = client.get(orders_url, {'expert-attendee_address_country': 'US'})
    assert res_attendee_us.status_code == 200
    content_attendee_us = res_attendee_us.content.decode()
    assert 'US001' not in content_attendee_us
    assert 'DE001' not in content_attendee_us

    # 6. Filter with empty country (All countries) shows both orders
    res_all = client.get(orders_url, {'expert-invoice_address_country': ''})
    assert res_all.status_code == 200
    content_all = res_all.content.decode()
    assert 'DE001' in content_all
    assert 'US001' in content_all


@pytest.mark.django_db
def test_expert_filter_form_widget_attributes(env):
    """Directly test that EventOrderExpertFilterForm assigns searchable select attrs to country fields."""
    with scope(organizer=env['organizer'], event=env['event']):
        form = EventOrderExpertFilterForm(event=env['event'])
        invoice_field = form.fields['invoice_address_country']
        attendee_field = form.fields['attendee_address_country']

        for field in [invoice_field, attendee_field]:
            assert field.choices[0] == ('', 'All countries')
            attrs = field.widget.attrs
            assert 'data-searchable-select' in attrs
            assert attrs['data-all-label'] == 'All countries'
            assert attrs['data-search-placeholder'] == 'Search'
            assert attrs['data-empty-text'] == 'No results'
