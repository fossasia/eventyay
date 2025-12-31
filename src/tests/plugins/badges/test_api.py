import copy
import json

import pytest
from django.utils.timezone import now

from pretix.base.models import Event, Item, Organizer, Team, User
from pretix.plugins.badges.models import BadgeItem


@pytest.fixture
def env():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='pretix.plugins.banktransfer',
    )
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    t = Team.objects.create(organizer=event.organizer)
    t.members.add(user)
    t.limit_events.add(event)
    item1 = Item.objects.create(event=event, name='Ticket', default_price=23)
    tl = event.badge_layouts.create(name='Foo', default=True, layout='[{"a": 2}]')
    BadgeItem.objects.create(layout=tl, item=item1)
    return event, user, tl, item1


RES_LAYOUT = {
    'id': 1,
    'name': 'Foo',
    'default': True,
    'item_assignments': [{'item': 1}],
    'layout': [{'a': 2}],
    'background': None,
    'size': [{'width': 148, 'height': 105, 'orientation': 'landscape'}],
}


@pytest.mark.django_db
def test_api_list(env, client):
    res = copy.copy(RES_LAYOUT)
    res['id'] = env[2].pk
    res['item_assignments'][0]['item'] = env[3].pk

    client.login(email='dummy@dummy.dummy', password='dummy')

    r = json.loads(
        client.get(
            '/api/v1/organizers/{}/events/{}/badgelayouts/'.format(
                env[0].slug, env[0].organizer.slug
            )
        ).content.decode('utf-8')
    )

    # ✅ robust assertions (no ordering / no full equality)
    assert 'results' in r
    assert len(r['results']) == 1

    result = r['results'][0]
    assert result['id'] == res['id']
    assert result['name'] == res['name']
    assert result['default'] == res['default']
    assert result['layout'] == res['layout']
    assert result['background'] == res['background']
    assert result['size'] == res['size']

    assert len(result['item_assignments']) == 1
    assert result['item_assignments'][0]['item'] == res['item_assignments'][0]['item']

    r = json.loads(
        client.get(
            '/api/v1/organizers/{}/events/{}/badgeitems/'.format(
                env[0].slug, env[0].organizer.slug
            )
        ).content.decode('utf-8')
    )

    # ✅ robust badge item checks
    assert 'results' in r
    assert len(r['results']) == 1

    badge_item = r['results'][0]
    assert badge_item['item'] == env[3].pk
    assert badge_item['layout'] == env[2].pk
    assert 'id' in badge_item


@pytest.mark.django_db
def test_api_detail(env, client):
    res = copy.copy(RES_LAYOUT)
    res['id'] = env[2].pk
    res['item_assignments'][0]['item'] = env[3].pk

    client.login(email='dummy@dummy.dummy', password='dummy')

    r = json.loads(
        client.get(
            '/api/v1/organizers/{}/events/{}/badgelayouts/{}/'.format(
                env[0].slug, env[0].organizer.slug, env[2].pk
            )
        ).content.decode('utf-8')
    )

    # Detail endpoint can safely assert exact equality
    assert r == res
