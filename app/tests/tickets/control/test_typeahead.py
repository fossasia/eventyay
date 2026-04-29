import datetime

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Product, ProductMetaProperty, Team, User


def _create_product_meta_typeahead_data():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Event One',
        slug='event-one',
        date_from=now(),
        plugins='pretix.plugins.banktransfer',
    )
    other_event = Event.objects.create(
        organizer=organizer,
        name='Event Two',
        slug='event-two',
        date_from=now() + datetime.timedelta(days=1),
        plugins='pretix.plugins.banktransfer',
    )
    event_property = ProductMetaProperty.objects.create(event=event, name='day', default='Monday')
    other_event_property = ProductMetaProperty.objects.create(event=other_event, name='day', default='Friday')
    product = Product.objects.create(event=event, name='Ticket One', default_price=23)
    other_product = Product.objects.create(event=other_event, name='Ticket Two', default_price=23)
    product.meta_values.create(property=event_property, value='Tuesday')
    other_product.meta_values.create(property=other_event_property, value='Thursday')
    return organizer, event, other_event


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_product_meta_values_for_limited_team_member(client):
    organizer, event, other_event = _create_product_meta_typeahead_data()
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=organizer, can_change_items=True)
    team.members.add(user)
    team.limit_events.add(event)
    client.force_login(user)

    response = client.get(
        reverse(
            'control:event.products.meta.typeahead',
            kwargs={'organizer': organizer.slug, 'event': event.slug},
        ),
        {'property': 'day', 'q': 'day'},
    )

    assert response.status_code == 200
    assert {result['name'] for result in response.json()['results']} == {'Monday', 'Tuesday'}


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_product_meta_values_for_full_access_team_member(client):
    organizer, event, other_event = _create_product_meta_typeahead_data()
    user = User.objects.create_user('full@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=organizer, can_change_items=True, all_events=True)
    team.members.add(user)
    client.force_login(user)

    response = client.get(
        reverse(
            'control:event.products.meta.typeahead',
            kwargs={'organizer': organizer.slug, 'event': event.slug},
        ),
        {'property': 'day', 'q': 'day'},
    )

    assert response.status_code == 200
    assert {result['name'] for result in response.json()['results']} == {'Friday', 'Monday', 'Thursday', 'Tuesday'}
