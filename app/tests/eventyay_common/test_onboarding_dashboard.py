"""Tests for the new-user onboarding dashboard."""

import re
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from eventyay.base.models import Event, Organizer, Team
from eventyay.base.meetup import EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE
from eventyay.eventyay_common.navigation import get_global_navigation
from eventyay.eventyay_common.onboarding import (
    _event_kind,
    format_profile_incomplete_message,
    get_missing_profile_fields,
    is_profile_incomplete,
    user_needs_onboarding,
)

User = get_user_model()


@pytest.fixture
def new_user(db):
    return User.objects.create_user(
        email='newuser@example.com',
        password='testpass123',
        locale='en',
    )


@pytest.fixture
def new_user_client(client, new_user):
    client.force_login(new_user)
    return client


@pytest.fixture
def public_upcoming_event(db):
    organizer = Organizer.objects.create(name='Public Org', slug='public-org')
    now = timezone.now()
    return Event.objects.create(
        organizer=organizer,
        name='Public Summit',
        slug='public-summit',
        date_from=now + timedelta(days=40),
        date_to=now + timedelta(days=42),
        currency='EUR',
        locale='en',
        is_public=True,
        live=True,
        startpage_visible=True,
        testmode=False,
        email='org@example.com',
    )


@pytest.mark.django_db
def test_new_user_needs_onboarding(new_user):
    assert user_needs_onboarding(new_user, request=None) is True
    assert is_profile_incomplete(new_user) is True
    assert get_missing_profile_fields(new_user) == ['full name', 'profile picture']
    assert 'full name' in format_profile_incomplete_message(get_missing_profile_fields(new_user))
    assert 'profile picture' in format_profile_incomplete_message(get_missing_profile_fields(new_user))


@pytest.mark.django_db
def test_profile_prompt_lists_only_missing_fields(new_user):
    new_user.fullname = 'Ada Lovelace'
    new_user.save(update_fields=['fullname'])
    missing = get_missing_profile_fields(new_user)
    assert missing == ['profile picture']
    assert format_profile_incomplete_message(missing) == (
        'Add your profile picture to finish your profile.'
    )


@pytest.mark.django_db
def test_user_with_organised_event_skips_onboarding(user, team, event):
    assert user_needs_onboarding(user, request=None) is False


@pytest.mark.django_db
def test_onboarding_dashboard_renders_for_new_user(new_user_client, public_upcoming_event):
    url = reverse('eventyay_common:dashboard')
    response = new_user_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'common-dashboard' in content
    assert 'Welcome to Eventyay!' in content
    assert 'Find events' in content
    assert 'Get started' in content
    assert 'Recommended events' in content
    assert 'Public Summit' in content
    assert 'Your upcoming events' not in content
    assert 'Complete your profile' in content
    assert 'Add your full name and profile picture to finish your profile.' in content
    assert 'cd-info' not in content


@pytest.mark.django_db
def test_onboarding_hides_organise_card_without_create_permission(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Organise an event' not in content
    assert 'Attend an event' in content
    assert 'Submit a talk' in content


@pytest.mark.django_db
def test_onboarding_shows_organise_card_with_create_permission(new_user, new_user_client):
    organizer = Organizer.objects.create(name='Create Org', slug='create-org')
    team = Team.objects.create(
        organizer=organizer,
        name='Creators',
        can_create_events=True,
        all_events=False,
    )
    team.members.add(new_user)

    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Organise an event' in content
    assert reverse('eventyay_common:events.add') in content


@pytest.mark.django_db
def test_organiser_dashboard_still_shown_for_event_managers(organizer_client, event):
    response = organizer_client.get(reverse('eventyay_common:dashboard'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Welcome to Eventyay!' not in content
    assert 'Your upcoming events' in content
    assert 'common-dashboard' in content
    assert 'cd-event-card' in content
    assert 'Quick actions' in content
    assert 'cd-info' not in content
    assert 'aria-label="Go to event"' in content
    assert '<label class="sr-only" for="dashboard_query">Go to event</label>' in content


@pytest.mark.django_db
def test_event_card_component_buttons_share_one_style(organizer_client, event):
    response = organizer_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert content.count('class="cd-module-btn"') == 3
    assert 'cd-module-btn--' not in content


def _declarations_for(css: str, *selectors: str) -> str:
    """The declarations of every rule that names one of ``selectors``."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    wanted = set(selectors)
    blocks = []
    for rule in re.finditer(r'([^{}]*)\{([^{}]*)\}', css):
        if wanted & {name.strip() for name in rule.group(1).split(',')}:
            blocks.append(rule.group(2))
    return '\n'.join(blocks)


@pytest.mark.django_db
def test_quick_action_icons_never_render_untoned(organizer_client, event):
    """The quick action icons build their class from a dynamic ``action.tone``.

    A tone without a rule of its own falls back to the base class, so every
    tone the dashboard renders must be coloured by one of the two.
    """
    response = organizer_client.get(reverse('eventyay_common:dashboard'))
    rendered_tones = set(re.findall(r'cd-action-card__icon--([a-z-]+)', response.content.decode()))
    assert rendered_tones, 'the organiser dashboard should render quick action icons'

    css = Path(finders.find('eventyay-common/css/common_dashboard.css')).read_text()
    for tone in sorted(rendered_tones):
        declarations = _declarations_for(css, '.cd-action-card__icon', f'.cd-action-card__icon--{tone}')
        assert 'background:' in declarations, f'the {tone} icon tone renders unstyled'


def test_talks_dashboard_text_uses_global_colours():
    """The Talks dashboard takes its text colours from the global stylesheet (#6280).

    ``stats.js`` moves the analytics filter menu to ``<body>``, outside
    ``.td-dashboard``, so the menu rules must use the global variables directly.
    """
    path = finders.find('eventyay-common/css/common_dashboard.css')
    assert path, 'eventyay-common/css/common_dashboard.css was not found by the static files finders'
    css = Path(path).read_text(encoding='utf-8')

    tokens = _declarations_for(css, '.td-dashboard')
    assert re.search(r'--td-text:\s*var\(--color-text\)', tokens)
    assert re.search(r'--td-muted:\s*var\(--color-text-muted\)', tokens)

    menu_head = _declarations_for(css, '.td-analytics-multi-menu-head')
    assert re.search(r'(?<![-\w])color:\s*var\(--color-text-muted\)', menu_head)
    menu_option = _declarations_for(css, '.td-analytics-multi-option')
    assert re.search(r'(?<![-\w])color:\s*var\(--color-text\)', menu_option)

    # Card titles and numbers are secondary text, so they use the muted grey (#6280 review).
    for selector in (
        '.td-kpi-label',
        '.td-kpi-value',
        '.td-action-title',
        '.td-action-count',
        '.td-upcoming-small',
        '.td-upcoming-large',
    ):
        declarations = _declarations_for(css, selector)
        assert re.search(r'(?<![-\w])color:\s*var\(--td-muted\)', declarations), f'{selector} should be muted grey'


@pytest.mark.django_db
def test_orders_empty_state(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:orders'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets yet' in content
    assert 'Browse events' in content
    assert 'No tickets match your filters.' not in content


@pytest.mark.django_db
def test_orders_empty_state_ignores_pagination_query(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:orders'), {'page': '1'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets yet' in content
    assert 'No tickets match your filters.' not in content


@pytest.mark.django_db
def test_orders_empty_state_ignores_blank_filter_values(new_user_client):
    response = new_user_client.get(
        reverse('eventyay_common:orders'),
        {'code': '', 'status': '', 'date_from': '', 'date_to': ''},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets yet' in content
    assert 'No tickets match your filters.' not in content


@pytest.mark.django_db
def test_orders_no_match_message_when_filter_active(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:orders'), {'code': 'NOMATCH'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No tickets match your filters.' in content
    assert 'No tickets yet' not in content


@pytest.mark.django_db
def test_sessions_empty_state(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:sessions'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No sessions yet' in content
    assert 'Find open calls' in content
    assert 'No sessions match your filters.' not in content


@pytest.mark.django_db
def test_sessions_empty_state_ignores_pagination_and_blank_search(new_user_client):
    response = new_user_client.get(
        reverse('eventyay_common:sessions'),
        {'page': '1', 'search': ''},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No sessions yet' in content
    assert 'No sessions match your filters.' not in content


@pytest.mark.django_db
def test_sessions_no_match_message_when_filter_active(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:sessions'), {'search': 'nomatch'})
    assert response.status_code == 200
    content = response.content.decode()
    assert 'No sessions match your filters.' in content
    assert 'No sessions yet' not in content


@pytest.mark.django_db
def test_private_events_are_not_recommended(new_user_client, db):
    organizer = Organizer.objects.create(name='Private Org', slug='private-org')
    now = timezone.now()
    Event.objects.create(
        organizer=organizer,
        name='Secret Meetup',
        slug='secret-meetup',
        date_from=now + timedelta(days=20),
        date_to=now + timedelta(days=21),
        currency='EUR',
        locale='en',
        is_public=False,
        live=True,
        startpage_visible=True,
        testmode=False,
        email='private@example.com',
    )
    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Secret Meetup' not in content


@pytest.mark.django_db
def test_global_navigation_labels(new_user_client):
    response = new_user_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'My orders' in content
    assert 'Dashboard' in content


@pytest.mark.django_db
def test_global_navigation_lists_plugin_items_before_organizers(rf):
    request = rf.get('/common/')
    request.resolver_match = MagicMock(url_name='dashboard')
    request.user = MagicMock(is_authenticated=True)
    request.user.teams.exists.return_value = True
    plugin_item = {'label': 'My exhibitions', 'url': '/common/exhibitions/', 'active': False, 'icon': 'building-o'}

    with patch('eventyay.eventyay_common.navigation.nav_global.send', return_value=[(None, [plugin_item])]):
        labels = [str(item['label']) for item in get_global_navigation(request)]

    assert labels == ['My orders', 'My sessions', 'My events', 'My exhibitions', 'Organizers']


@pytest.mark.django_db
def test_global_navigation_keeps_plugin_children_under_organizers(rf):
    request = rf.get('/common/')
    request.resolver_match = MagicMock(url_name='dashboard')
    request.user = MagicMock(is_authenticated=True)
    request.user.teams.exists.return_value = True
    child = {
        'label': 'Organizer tool',
        'url': '/common/organizer-tool/',
        'active': False,
        'parent': reverse('eventyay_common:organizers'),
    }

    with patch('eventyay.eventyay_common.navigation.nav_global.send', return_value=[(None, [child])]):
        nav = get_global_navigation(request)

    organizers = nav[-1]
    assert str(organizers['label']) == 'Organizers'
    assert child in organizers['children']
    assert all(item is not child for item in nav)


@pytest.mark.django_db
def test_event_kind_labels_event_series_and_meetup(event):
    assert _event_kind(event)['kind'] == 'event'
    assert _event_kind(event)['label'] == 'Event'

    event.has_subevents = True
    assert _event_kind(event)['kind'] == 'series'
    assert _event_kind(event)['label'] == 'Series'

    event.has_subevents = False
    event.settings.set(EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE)
    assert _event_kind(event)['kind'] == 'meetup'
    assert _event_kind(event)['label'] == 'Meetup'
