from unittest.mock import MagicMock, patch

import pytest
from django.core import mail as djmail
from django.urls import NoReverseMatch
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.base.services.teams import get_team_invitation_url, send_team_invite
from eventyay.helpers.urls import build_absolute_uri


@pytest.fixture
def organizer():
    o = Organizer.objects.create(name='Test Org', slug='test-org')
    with scope(organizer=o):
        yield o


@pytest.fixture
def user():
    return User.objects.create_user('member@example.com', 'dummy_pass')


@pytest.mark.django_db
def test_get_team_invitation_url_standard_team(organizer):
    team = Team.objects.create(organizer=organizer, name='Admin Team', teamshifts_role='')
    url = get_team_invitation_url(team)
    assert url.endswith(f'/common/organizer/test-org/team/{team.pk}')


def _create_event(organizer, slug, plugins='teamshifts'):
    return Event.objects.create(
        organizer=organizer,
        name=slug,
        slug=slug,
        date_from=now(),
        plugins=plugins,
    )


@pytest.fixture
def teamshifts_installed():
    pytest.importorskip('teamshifts')


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['coordinator', 'lead'])
def test_get_team_invitation_url_single_event_links_to_event_dashboard(organizer, teamshifts_installed, role):
    event = _create_event(organizer, 'conf')
    team = Team.objects.create(organizer=organizer, name='Shifts Team', teamshifts_role=role, all_events=True)
    url = get_team_invitation_url(team)
    assert url.endswith(f'/teamshifts/event/test-org/{event.slug}/')


@pytest.mark.django_db
def test_get_team_invitation_url_limited_team_links_to_its_event(organizer, teamshifts_installed):
    _create_event(organizer, 'other')
    event = _create_event(organizer, 'mine')
    team = Team.objects.create(organizer=organizer, name='Lead Team', teamshifts_role='lead', all_events=False)
    team.limit_events.add(event)
    url = get_team_invitation_url(team)
    assert url.endswith('/teamshifts/event/test-org/mine/')


@pytest.mark.django_db
def test_get_team_invitation_url_multiple_events_links_to_common_dashboard(organizer):
    _create_event(organizer, 'one')
    _create_event(organizer, 'two')
    team = Team.objects.create(organizer=organizer, name='Shifts Team', teamshifts_role='coordinator', all_events=True)
    assert get_team_invitation_url(team) == build_absolute_uri('eventyay_common:dashboard')


@pytest.mark.django_db
def test_get_team_invitation_url_single_eligible_event_among_several_links_to_it(organizer, teamshifts_installed):
    _create_event(organizer, 'plain', plugins='')
    _create_event(organizer, 'shifts')
    team = Team.objects.create(organizer=organizer, name='Shifts Team', teamshifts_role='lead', all_events=True)
    assert get_team_invitation_url(team).endswith('/teamshifts/event/test-org/shifts/')


@pytest.mark.django_db
def test_get_team_invitation_url_no_teamshifts_event_links_to_common_dashboard(organizer):
    _create_event(organizer, 'plain', plugins='')
    team = Team.objects.create(organizer=organizer, name='Shifts Team', teamshifts_role='coordinator', all_events=True)
    assert get_team_invitation_url(team) == build_absolute_uri('eventyay_common:dashboard')


@pytest.mark.django_db
def test_get_team_invitation_url_ignores_events_outside_team_scope(organizer):
    _create_event(organizer, 'outside')
    inside = _create_event(organizer, 'inside', plugins='')
    team = Team.objects.create(organizer=organizer, name='Lead Team', teamshifts_role='lead', all_events=False)
    team.limit_events.add(inside)
    assert get_team_invitation_url(team) == build_absolute_uri('eventyay_common:dashboard')


@pytest.mark.django_db
def test_get_team_invitation_url_unavailable_plugin_route_links_to_common_dashboard(organizer):
    _create_event(organizer, 'conf')
    team = Team.objects.create(organizer=organizer, name='Lead Team', teamshifts_role='lead', all_events=True)
    with patch(
        'eventyay.base.services.teams.build_absolute_uri',
        side_effect=[NoReverseMatch('Plugin not installed'), 'http://localhost/common/'],
    ):
        assert get_team_invitation_url(team) == 'http://localhost/common/'


@pytest.mark.django_db
@pytest.mark.parametrize('all_events', [True, False])
def test_get_team_invitation_url_unsaved_teamshifts_team_links_to_common_dashboard(organizer, all_events):
    team = Team(organizer=organizer, name='Unsaved', teamshifts_role='lead', all_events=all_events)
    assert get_team_invitation_url(team) == build_absolute_uri('eventyay_common:dashboard')


@pytest.mark.django_db
def test_get_team_invitation_url_standard_team_no_pk(organizer):
    mock_team = MagicMock(organizer=organizer, teamshifts_role='', pk=None)
    url = get_team_invitation_url(mock_team)
    assert url.endswith('/common/organizer/test-org/teams')


@pytest.mark.django_db
def test_send_team_invite_links_to_invitation_page(organizer, user):
    djmail.outbox = []
    team = Team.objects.create(organizer=organizer, name='Shifts Team', teamshifts_role='coordinator', all_events=True)
    invite = team.invites.create(email=user.email, user=user)

    assert send_team_invite(invite) is True

    assert len(djmail.outbox) == 1
    assert djmail.outbox[0].subject == 'Invitation to join the “Shifts Team” team for “Test Org”'
    assert invite.invitation_url in djmail.outbox[0].body
