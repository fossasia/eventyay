import copy
import json

import pytest
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Product, Team, User
from eventyay.plugins.badges.models import BadgeProduct


@pytest.fixture
def env():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.badges',
    )
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=event.organizer)
    team.members.add(user)
    team.limit_events.add(event)
    product = Product.objects.create(event=event, name='Ticket', default_price=23)
    layout = event.badge_layouts.create(name='Foo', default=True, layout='[{"a": 2}]')
    BadgeProduct.objects.create(layout=layout, product=product)
    return event, user, layout, product


RES_LAYOUT = {
    'id': 1,
    'name': 'Foo',
    'default': True,
    'allow_customization': False,
    'product_assignments': [{'product': 1}],
    'layout': [{'a': 2}],
    'ask_user_fields': [],
    'background': None,
    'size': [{'width': 148, 'height': 105, 'orientation': 'landscape'}],
}


@pytest.mark.django_db
def test_api_list(env, client):
    res = copy.deepcopy(RES_LAYOUT)
    res['id'] = env[2].pk
    res['product_assignments'][0]['product'] = env[3].pk
    client.login(email='dummy@dummy.dummy', password='dummy')
    response = json.loads(
        client.get(
            '/api/v1/organizers/{}/events/{}/badgelayouts/'.format(env[0].organizer.slug, env[0].slug)
        ).content.decode('utf-8')
    )
    assert response['results'] == [res]

    response = json.loads(
        client.get(
            '/api/v1/organizers/{}/events/{}/badgeitems/'.format(env[0].organizer.slug, env[0].slug)
        ).content.decode('utf-8')
    )
    assert response['results'] == [
        {
            'product': env[3].pk,
            'layout': env[2].pk,
            'id': env[2].product_assignments.first().pk,
        }
    ]


@pytest.mark.django_db
def test_api_detail(env, client):
    res = copy.deepcopy(RES_LAYOUT)
    res['id'] = env[2].pk
    res['product_assignments'][0]['product'] = env[3].pk
    client.login(email='dummy@dummy.dummy', password='dummy')
    response = json.loads(
        client.get(
            '/api/v1/organizers/{}/events/{}/badgelayouts/{}/'.format(
                env[0].organizer.slug,
                env[0].slug,
                env[2].pk,
            )
        ).content.decode('utf-8')
    )
    assert response == res
