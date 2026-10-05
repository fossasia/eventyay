import pytest
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import Organizer, Team, User


@pytest.mark.django_db
def test_organizers_empty_state_when_search_has_no_match(client):
    with scopes_disabled():
        user = User.objects.create_user('testuser@eventyay.com', 'testpassword')
        orga = Organizer.objects.create(name='FOSSASIA', slug='fossasia')
        team = Team.objects.create(
            organizer=orga,
            name='Admin Team',
            can_create_events=True,
            can_change_organizer_settings=True,
        )
        team.members.add(user)

    client.login(email='testuser@eventyay.com', password='testpassword')
    url = reverse('eventyay_common:organizers')

    # 1. Search with no matches
    response = client.get(url, {'query': 'nonexistent'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No organizers found.' in content
    assert 'fossasia' not in content

    # 2. Search with matches
    response_match = client.get(url, {'query': 'FOSSASIA'})
    assert response_match.status_code == 200
    content_match = response_match.content.decode()
    assert 'No organizers found.' not in content_match
    assert 'FOSSASIA' in content_match

    # 3. Normal list without query
    response_all = client.get(url)
    assert response_all.status_code == 200
    content_all = response_all.content.decode()
    assert 'No organizers found.' not in content_all
    assert 'FOSSASIA' in content_all


@pytest.mark.django_db
def test_organizers_empty_state_when_no_organizers_exist(client):
    with scopes_disabled():
        User.objects.create_user('emptyuser@eventyay.com', 'testpassword')

    client.login(email='emptyuser@eventyay.com', password='testpassword')
    url = reverse('eventyay_common:organizers')

    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No organizers found.' in content
