"""Tests for the new-user onboarding dashboard."""

import re
from datetime import timedelta
from pathlib import Path

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.meetup import EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE
from eventyay.base.models import Event, Order, Organizer, Submission, SubmissionType, Team
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
    user = User.objects.create_user(
        email='newuser@example.com',
        password='testpass123',
        locale='en',
    )
    EmailAddress.objects.create(
        user=user,
        email=user.email,
        verified=True,
        primary=True,
    )
    return user


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
    assert format_profile_incomplete_message(missing) == ('Add your profile picture to finish your profile.')


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
def test_event_card_role_aware_module_action_buttons(organizer_client, event):
    response = organizer_client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'cd-module-btn' in content
    assert 'Tickets' in content
    assert 'Talks' in content
    assert 'Video' in content


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
    assert 'My Tickets' in content
    assert 'Dashboard' in content


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


@pytest.mark.django_db
def test_attendee_dashboard_view(client, new_user, public_upcoming_event):
    with scopes_disabled():
        Order.objects.create(
            event=public_upcoming_event,
            email=new_user.email,
            status=Order.STATUS_PAID,
            code='ATTEND1',
            datetime=timezone.now(),
            total=10,
        )
    client.force_login(new_user)
    response = client.get(reverse('eventyay_common:dashboard'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Attendee' in content
    assert 'My tickets' in content
    assert 'ATTEND1' in content
    assert 'View ticket' in content
    assert 'compact-organising-title' not in content


@pytest.mark.django_db
def test_speaker_dashboard_view(client, new_user, public_upcoming_event):
    new_user.fullname = 'Speaker User'
    new_user.save()
    with scopes_disabled():
        sub_type = SubmissionType.objects.create(
            event=public_upcoming_event,
            name='Standard Talk',
        )
        sub = Submission.objects.create(
            event=public_upcoming_event,
            submission_type=sub_type,
            title='My Great Talk',
            state='accepted',
        )
        sub.speakers.add(new_user)
    client.force_login(new_user)
    response = client.get(reverse('eventyay_common:dashboard'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Speaker' in content
    assert 'My sessions and proposals' in content
    assert 'My Great Talk' in content
    assert 'My session' in content
    assert 'Session confirmation required' in content
    assert 'compact-tickets-title' not in content
    assert 'compact-organising-title' not in content


@pytest.mark.django_db
def test_needs_your_attention_unpaid_order(client, new_user, public_upcoming_event):
    with scopes_disabled():
        Order.objects.create(
            event=public_upcoming_event,
            email=new_user.email,
            status=Order.STATUS_PENDING,
            require_approval=False,
            code='PENDING1',
            datetime=timezone.now(),
            total=20,
        )
    client.force_login(new_user)
    response = client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'Needs your attention' in content
    assert 'Payment pending' in content
    assert 'Pay now' in content


@pytest.mark.django_db
def test_unverified_user_cannot_see_orders(client, db, public_upcoming_event):
    unverified_user = User.objects.create_user(
        email='unverified@example.com',
        password='testpass123',
        locale='en',
    )
    with scopes_disabled():
        Order.objects.create(
            event=public_upcoming_event,
            email=unverified_user.email,
            status=Order.STATUS_PAID,
            code='SECRET99',
            datetime=timezone.now(),
            total=10,
        )
    client.force_login(unverified_user)
    response = client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    assert 'SECRET99' not in content

    orders_response = client.get(reverse('eventyay_common:orders'))
    assert 'SECRET99' not in orders_response.content.decode()

    EmailAddress.objects.create(
        user=unverified_user,
        email=unverified_user.email,
        verified=True,
        primary=True,
    )
    orders_response = client.get(reverse('eventyay_common:orders'))
    assert 'SECRET99' in orders_response.content.decode()


@pytest.mark.django_db
def test_unverified_speaker_sees_recent_activity(client, public_upcoming_event):
    speaker = User.objects.create_user(
        email='speaker_unverified@example.com',
        password='testpass123',
        locale='en',
    )
    with scopes_disabled():
        sub_type = SubmissionType.objects.create(
            event=public_upcoming_event,
            name='Standard Talk',
        )
        sub = Submission.objects.create(
            event=public_upcoming_event,
            submission_type=sub_type,
            title='Unverified Speaker Talk',
            state='accepted',
        )
        sub.speakers.add(speaker)

    client.force_login(speaker)
    response = client.get(reverse('eventyay_common:dashboard'))
    sub_url = reverse(
        'cfp:event.user.submission.edit',
        kwargs={
            'organizer': public_upcoming_event.organizer.slug,
            'event': public_upcoming_event.slug,
            'code': sub.code,
        },
    )
    activity = response.context['recent_activity']
    assert any(item['url'] == sub_url and 'Unverified Speaker Talk' in item['title'] for item in activity)


@pytest.mark.django_db
def test_organiser_secondary_links_respect_permissions(client, public_upcoming_event):
    org_user = User.objects.create_user(
        email='org_user@example.com',
        password='testpass123',
        locale='en',
    )
    with scopes_disabled():
        t = Team.objects.create(
            organizer=public_upcoming_event.organizer,
            name='Orders Only Team',
            can_change_event_settings=False,
            can_change_items=False,
            can_view_orders=True,
            can_change_orders=False,
        )
        t.members.add(org_user)
        t.limit_events.add(public_upcoming_event)

    client.force_login(org_user)
    response = client.get(reverse('eventyay_common:dashboard'))
    content = response.content.decode()
    control_tickets_url = reverse(
        'control:event.index',
        kwargs={'organizer': public_upcoming_event.organizer.slug, 'event': public_upcoming_event.slug},
    )
    assert control_tickets_url in content
    settings_url = reverse(
        'eventyay_common:event.update',
        kwargs={'organizer': public_upcoming_event.organizer.slug, 'event': public_upcoming_event.slug},
    )
    assert settings_url not in content
