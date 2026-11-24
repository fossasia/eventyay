import importlib

import pytest
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Team, User
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.base.services.organizer_creation import create_core_team, is_event_core_team_member
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.forms.organizer_forms.team_form import TeamForm as ControlTeamForm
from eventyay.event.forms import TeamForm as TalkTeamForm


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner@example.com', 'owner')


@pytest.fixture
def core_team(organizer, owner):
    return create_core_team(organizer, owner)


@pytest.mark.django_db
def test_create_core_team_sets_flag_and_member(core_team, owner):
    assert core_team.is_core_team
    assert core_team.all_events
    assert list(core_team.members.all()) == [owner]


@pytest.mark.django_db
def test_core_team_member_passes(core_team, owner, event):
    assert is_event_core_team_member(owner, event)


@pytest.mark.django_db
def test_member_of_other_team_with_all_permissions_fails(organizer, event):
    user = User.objects.create_user('admin-team@example.com', 'x')
    team = Team.objects.create(
        organizer=organizer,
        name='Administrators',
        all_events=True,
        can_change_teams=True,
        can_change_organizer_settings=True,
        can_change_event_settings=True,
        can_change_orders=True,
    )
    team.members.add(user)
    assert not is_event_core_team_member(user, event)


@pytest.mark.django_db
def test_non_member_and_anonymous_fail(core_team, event):
    stranger = User.objects.create_user('stranger@example.com', 'x')
    assert not is_event_core_team_member(stranger, event)
    assert not is_event_core_team_member(AnonymousUser(), event)


@pytest.mark.django_db
def test_inactive_core_member_fails(core_team, owner, event):
    owner.is_active = False
    owner.save()
    assert not is_event_core_team_member(owner, event)


@pytest.mark.django_db
def test_core_team_limited_to_other_event_fails(organizer, event):
    other_event = Event.objects.create(organizer=organizer, name='Other', slug='other', date_from=now())
    user = User.objects.create_user('limited@example.com', 'x')
    team = Team.objects.create(organizer=organizer, name='Limited core', is_core_team=True, all_events=False)
    team.limit_events.add(other_event)
    team.members.add(user)
    assert not is_event_core_team_member(user, event)
    assert is_event_core_team_member(user, other_event)


@pytest.mark.django_db
def test_core_team_of_other_organizer_fails(event):
    other_organizer = Organizer.objects.create(name='Other', slug='otherorg')
    user = User.objects.create_user('other-owner@example.com', 'x')
    create_core_team(other_organizer, user)
    assert not is_event_core_team_member(user, event)


@pytest.mark.django_db
def test_core_flag_is_not_a_team_permission(core_team, organizer, event):
    assert 'is_core_team' not in Team._permission_field_names()
    assert 'is_core_team' not in core_team.permission_set()
    token = TeamAPIToken.objects.create(team=core_team, name='Token')
    assert 'is_core_team' not in token.get_event_permission_set(organizer, event)


def test_core_flag_not_editable_in_team_forms():
    assert 'is_core_team' not in ControlTeamForm.base_fields
    assert 'is_core_team' not in TalkTeamForm.base_fields


@pytest.mark.django_db
def test_organizer_create_view_creates_flagged_core_team(client):
    GlobalSettingsObject().settings.set('allow_all_users_create_organizer', True)
    user = User.objects.create_user('creator@example.com', 'creator')
    client.force_login(user)
    response = client.post(
        reverse('eventyay_common:organizers.add'),
        {'name': 'New organizer', 'slug': 'new-organizer'},
    )
    assert response.status_code == 302
    organizer = Organizer.objects.get(slug='new-organizer')
    team = organizer.teams.get()
    assert team.is_core_team
    assert team.name == 'Core Organizing Team'
    assert list(team.members.all()) == [user]


OWNER_ACCESS = {'all_events': True, 'can_change_teams': True, 'can_change_organizer_settings': True}


def run_backfill():
    migration = importlib.import_module('eventyay.base.migrations.0094_team_is_core_team')
    migration.flag_core_teams(apps, None)


def core_team_ids():
    return set(Team.objects.filter(is_core_team=True).values_list('pk', flat=True))


@pytest.mark.django_db
def test_backfill_flags_oldest_owner_team_whatever_its_name(organizer):
    legacy = Team.objects.create(organizer=organizer, name='Administrators', **OWNER_ACCESS)
    Team.objects.create(organizer=organizer, name='Second admins', **OWNER_ACCESS)
    Team.objects.create(organizer=organizer, name='Reviewers', all_events=True, is_reviewer=True)
    run_backfill()
    assert core_team_ids() == {legacy.pk}


@pytest.mark.django_db
def test_backfill_flags_renamed_and_translated_core_teams(organizer):
    renamed = Team.objects.create(organizer=organizer, name='Board', **OWNER_ACCESS)
    other_organizer = Organizer.objects.create(name='Other', slug='otherorg')
    translated = Team.objects.create(organizer=other_organizer, name='Kern-Organisationsteam', **OWNER_ACCESS)
    run_backfill()
    assert core_team_ids() == {renamed.pk, translated.pk}


@pytest.mark.django_db
def test_backfill_skips_older_teams_without_owner_access(organizer):
    Team.objects.create(organizer=organizer, name='Core Organizing Team', all_events=True, can_change_orders=True)
    owner = Team.objects.create(organizer=organizer, name='Owners', **OWNER_ACCESS)
    run_backfill()
    assert core_team_ids() == {owner.pk}


@pytest.mark.django_db
def test_backfill_leaves_organizer_without_owner_team_alone(organizer):
    Team.objects.create(organizer=organizer, name='Helpers', all_events=True, can_change_teams=True)
    Team.objects.create(
        organizer=organizer, name='Limited admins', can_change_teams=True, can_change_organizer_settings=True
    )
    run_backfill()
    assert core_team_ids() == set()
