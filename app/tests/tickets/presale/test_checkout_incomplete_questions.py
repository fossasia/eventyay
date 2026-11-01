from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Organizer, Product, Quota


@pytest.fixture
def event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=organizer,
            name='Dummy',
            slug='dummy',
            date_from=now() + timedelta(days=30),
            plugins='eventyay.plugins.banktransfer',
            live=True,
            tickets_published=True,
        )
        event.settings.payment_banktransfer__enabled = True
        event.settings.require_registered_account_for_tickets = False
    with scope(organizer=organizer, event=event):
        product = Product.objects.create(event=event, name='Ticket', default_price=10, admission=True)
        quota = Quota.objects.create(event=event, name='Tickets', size=10)
        quota.products.add(product)
    return event


def add_ticket_to_cart(client, event):
    with scope(organizer=event.organizer, event=event):
        product = event.products.get()
    client.get('/dummy/dummy/')
    client.post('/dummy/dummy/cart/add', {f'item_{product.pk}': '1'})


def set_cart_email(client, event, email):
    session = client.session
    for cart in session['carts'].values():
        cart['email'] = email
    session.save()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_later_step_without_email_redirects_to_questions(client, event):
    add_ticket_to_cart(client, event)

    response = client.get('/dummy/dummy/checkout/confirm/')

    assert response.status_code == 302
    assert response['Location'].endswith('/checkout/questions/')
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert 'Please enter a valid email address.' in messages


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_later_step_without_attendee_name_redirects_to_questions(client, event):
    event.settings.attendee_names_asked = True
    event.settings.attendee_names_required = True
    add_ticket_to_cart(client, event)
    set_cart_email(client, event, 'dummy@dummy.test')

    response = client.get('/dummy/dummy/checkout/confirm/')

    assert response.status_code == 302
    assert response['Location'].endswith('/checkout/questions/')
    messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert 'Please fill in answers to all required questions.' in messages
