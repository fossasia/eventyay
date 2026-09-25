from unittest.mock import patch

import pytest
from django.core import mail as djmail
from django_scopes import scope

from eventyay.base.models import Organizer, Team, User
from eventyay.base.services.teams import get_team_invitation_url, send_team_invitation_email


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
    assert url.endswith('/common/organizer/test-org/teams')


@pytest.mark.django_db
def test_get_team_invitation_url_teamshifts_coordinator(organizer):
    team = Team.objects.create(organizer=organizer, name='Coordinator Team', teamshifts_role='coordinator')
    url = get_team_invitation_url(team)
    assert url.endswith('/teamshifts/organizer/test-org/')


@pytest.mark.django_db
def test_get_team_invitation_url_teamshifts_lead(organizer):
    team = Team.objects.create(organizer=organizer, name='Lead Team', teamshifts_role='lead')
    url = get_team_invitation_url(team)
    assert url.endswith('/teamshifts/organizer/test-org/')


@pytest.mark.django_db
def test_get_team_invitation_url_plugin_fallback(organizer):
    team = Team.objects.create(organizer=organizer, name='Lead Team', teamshifts_role='lead')
    with patch('eventyay.helpers.urls.build_absolute_uri', side_effect=[Exception('Plugin not installed'), 'http://localhost/fallback/']):
        url = get_team_invitation_url(team)
        assert url == 'http://localhost/fallback/'


@pytest.mark.django_db
def test_send_team_invitation_email_explicit_url(organizer, user):
    djmail.outbox = []
    success = send_team_invitation_email(
        user=user,
        organizer_name=organizer.name,
        team_name='Test Team',
        url='http://localhost:8000/custom/invitation/url',
        locale='en',
        is_registered_user=True,
    )
    assert success is True
    assert len(djmail.outbox) == 1
    assert 'http://localhost:8000/custom/invitation/url' in djmail.outbox[0].body


@pytest.mark.django_db
def test_send_team_invitation_email_with_teamshifts_team(organizer, user):
    djmail.outbox = []
    team = Team.objects.create(organizer=organizer, name='Shifts Team', teamshifts_role='coordinator')
    success = send_team_invitation_email(
        user=user,
        organizer_name=organizer.name,
        team_name=team.name,
        team=team,
        locale='en',
        is_registered_user=True,
    )
    assert success is True
    assert len(djmail.outbox) == 1
    assert '/teamshifts/organizer/test-org/' in djmail.outbox[0].body
