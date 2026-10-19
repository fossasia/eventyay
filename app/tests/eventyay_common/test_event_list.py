from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Organizer, Team, User


@pytest.mark.django_db
def test_events_empty_state_when_search_has_no_match(client):
    with scopes_disabled():
        user = User.objects.create_user('testuser@eventyay.com', 'testpassword')
        orga = Organizer.objects.create(name='FOSSASIA', slug='fossasia')
        team = Team.objects.create(
            organizer=orga,
            name='Admin Team',
            all_events=True,
            can_create_events=True,
            can_change_event_settings=True,
        )
        team.members.add(user)
        now = timezone.now()
        Event.objects.create(
            organizer=orga,
            name='Open Tech Summit',
            slug='ots',
            date_from=now + timedelta(days=30),
            date_to=now + timedelta(days=32),
            currency='USD',
            locale='en',
        )

    client.login(email='testuser@eventyay.com', password='testpassword')
    url = reverse('eventyay_common:events')

    # 1. Search with no matches
    response = client.get(url, {'query': 'nonexistent'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No events found.' in content
    assert 'Open Tech Summit' not in content

    # 2. Search with matches
    response_match = client.get(url, {'query': 'Open Tech Summit'})
    assert response_match.status_code == 200
    content_match = response_match.content.decode()
    assert 'No events found.' not in content_match
    assert 'Open Tech Summit' in content_match

    # 3. Normal list without query
    response_all = client.get(url)
    assert response_all.status_code == 200
    content_all = response_all.content.decode()
    assert 'No events found.' not in content_all
    assert 'Open Tech Summit' in content_all


@pytest.mark.django_db
def test_events_empty_state_when_no_events_exist(client):
    with scopes_disabled():
        User.objects.create_user('emptyuser@eventyay.com', 'testpassword')

    client.login(email='emptyuser@eventyay.com', password='testpassword')
    url = reverse('eventyay_common:events')

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No events yet' in content
