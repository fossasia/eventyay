from datetime import timedelta
import re

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
            live=True,
        )
        Event.objects.create(
            organizer=orga,
            name='Draft Meetup',
            slug='draft-meetup',
            date_from=now + timedelta(days=40),
            date_to=now + timedelta(days=41),
            currency='USD',
            locale='en',
            live=False,
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

    # 3. The events page opens on the Live tab
    response_all = client.get(url)
    assert response_all.status_code == 200
    content_all = response_all.content.decode()
    assert 'No events found.' not in content_all
    assert 'Open Tech Summit' in content_all
    assert 'Draft Meetup' not in content_all
    assert re.search(r'<li role="presentation" class="active">\s*<a [^>]*>Live</a>', content_all)
    for label in ('Draft', 'Past', 'All'):
        assert not re.search(
            r'<li role="presentation" class="active">\s*<a [^>]*>' + label + r'</a>',
            content_all,
        )
    assert response_all.context['active_event_tab'] == 'live'
    assert 'fa-caret-right stats-arrow stats-arrow-collapsed' in content_all
    assert 'fa-caret-up stats-arrow stats-arrow-expanded' in content_all

    response_draft = client.get(url, {'tab': 'draft'})
    content_draft = response_draft.content.decode()
    assert response_draft.context['active_event_tab'] == 'draft'
    assert 'Draft Meetup' in content_draft
    assert 'Open Tech Summit' not in content_draft

    response_every = client.get(url, {'tab': 'all'})
    content_every = response_every.content.decode()
    assert response_every.context['active_event_tab'] == 'all'
    assert 'Open Tech Summit' in content_every
    assert 'Draft Meetup' in content_every

    response_conflict = client.get(url, {'tab': 'draft', 'status': 'live'})
    content_conflict = response_conflict.content.decode()
    assert response_conflict.context['active_event_tab'] == 'draft'
    assert 'Draft Meetup' in content_conflict
    assert 'Open Tech Summit' not in content_conflict

    response_blank_status = client.get(url, {'tab': 'live', 'status': ''})
    content_blank_status = response_blank_status.content.decode()
    assert response_blank_status.context['active_event_tab'] == 'live'
    assert 'Open Tech Summit' in content_blank_status
    assert 'Draft Meetup' not in content_blank_status

    response_unknown = client.get(url, {'status': 'unknown', 'query': 'Open Tech'})
    content_unknown = response_unknown.content.decode()
    assert response_unknown.context['active_event_tab'] == 'live'
    assert 'Open Tech Summit' in content_unknown
    assert 'Draft Meetup' not in content_unknown

    response_paged = client.get(url, {'tab': 'all', 'page': '1'})
    live_href = re.search(
        r'class="events-overview-tabs".*?href="([^"]*)"[^>]*>Live</a>',
        response_paged.content.decode(),
        re.S,
    )
    assert live_href
    assert 'page=' not in live_href.group(1)


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

    response_page = client.get(url, {'page_size': '50'})
    assert 'No events yet' in response_page.content.decode()

    response_tab = client.get(url, {'tab': 'past', 'status': 'past', 'page_size': '50'})
    tab_content = response_tab.content.decode()
    assert 'No events yet' not in tab_content
    assert 'No events found.' in tab_content
