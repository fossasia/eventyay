import importlib

import pytest
from django.apps import apps as django_apps
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import Event, Organizer, Team
from eventyay.base.models.auth import User
from eventyay.base.services.core_team import is_event_core_team_member
from eventyay.base.services.organizer_creation import create_core_team
from eventyay.control.forms.organizer_forms.team_form import TeamForm


MIGRATION = importlib.import_module('eventyay.base.migrations.0094_team_is_core_team')

pytestmark = pytest.mark.django_db


@pytest.fixture
def organizer():
    return Organizer.objects.create(name='Core Org', slug='core-org')


@pytest.fixture
def event(organizer):
    return Event.objects.create(
        organizer=organizer,
        name='Core Event',
        slug='core-event',
        date_from=now(),
    )


@pytest.fixture
def core_member(organizer):
    user = User.objects.create_user('core@example.org', 'password')
    return user


def _member(email):
    return User.objects.create_user(email, 'password')


def test_create_core_team_flags_the_team(organizer, core_member):
    team = create_core_team(organizer, core_member)

    assert team.is_core_team is True
    assert team.members.filter(pk=core_member.pk).exists()


def test_the_flag_is_not_a_team_permission(organizer):
    team = organizer.teams.create(name='Admins', all_events=True, is_core_team=True)

    assert 'is_core_team' not in Team._permission_field_names()
    assert 'is_core_team' not in team.permission_set()
    assert team.has_permission('can_change_orders') is False


def test_organizer_team_form_cannot_grant_the_flag(organizer):
    form = TeamForm(organizer=organizer)

    assert 'is_core_team' not in form.fields
    assert 'is_core_team' not in TeamForm.Meta.fields


def test_editing_a_core_team_through_the_form_keeps_the_flag(organizer, core_member):
    team = create_core_team(organizer, core_member)
    form = TeamForm(organizer=organizer, instance=team, data={'name': 'Renamed team'})

    assert 'is_core_team' not in form.fields
    assert team.is_core_team is True


def test_core_team_member_is_recognized_for_the_event(organizer, event, core_member):
    team = create_core_team(organizer, core_member)

    assert is_event_core_team_member(core_member, event) is True

    team.members.remove(core_member)
    assert is_event_core_team_member(core_member, event) is False


def test_regular_team_member_is_not_a_core_team_member(organizer, event):
    user = _member('reviewer@example.org')
    team = organizer.teams.create(name='Reviewers', all_events=True, is_exhibition_reviewer=True)
    team.members.add(user)

    assert is_event_core_team_member(user, event) is False


def test_non_member_and_anonymous_user_are_not_core_team_members(organizer, event, core_member):
    create_core_team(organizer, core_member)
    outsider = _member('outsider@example.org')
    anonymous = User()

    assert is_event_core_team_member(outsider, event) is False
    assert is_event_core_team_member(anonymous, event) is False
    assert is_event_core_team_member(None, event) is False


def test_migration_flags_translated_core_team_names(organizer):
    english = organizer.teams.create(name='Core Organizing Team', all_events=True)
    other_organizer = Organizer.objects.create(name='German Org', slug='german-org')
    german = other_organizer.teams.create(name='Kern-Organisationsteam', all_events=True)
    regular = organizer.teams.create(name='Reviewers', all_events=True)

    MIGRATION.flag_existing_core_teams(django_apps, None)

    english.refresh_from_db()
    german.refresh_from_db()
    regular.refresh_from_db()
    assert english.is_core_team is True
    assert german.is_core_team is True
    assert regular.is_core_team is False


def test_migration_flags_at_most_one_team_per_organizer(organizer):
    first = organizer.teams.create(name='Core Organizing Team', all_events=True)
    second = organizer.teams.create(name='Kern-Organisationsteam', all_events=True)

    MIGRATION.flag_existing_core_teams(django_apps, None)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_core_team is True
    assert second.is_core_team is False


@override_settings(DEBUG=True)
def test_organizer_teams_page_shows_the_core_badge_read_only(organizer, core_member, client):
    team = create_core_team(organizer, core_member)
    client.force_login(core_member)

    response = client.get(reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug}))

    assert response.status_code == 200
    content = response.content.decode()
    assert f'team-core-flag-{team.pk}' in content
    assert 'name="is_core_team"' not in content


@override_settings(DEBUG=True)
def test_regular_teams_do_not_show_the_core_badge(organizer, core_member, client):
    create_core_team(organizer, core_member)
    regular = organizer.teams.create(name='Reviewers', all_events=True, can_view_orders=True)
    client.force_login(core_member)

    response = client.get(reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug}))

    assert response.status_code == 200
    assert f'team-core-flag-{regular.pk}' not in response.content.decode()


@override_settings(DEBUG=True)
def test_new_organizer_gets_a_flagged_core_team(organizer, core_member, client):
    client.force_login(core_member)

    response = client.post(
        reverse('eventyay_common:organizers.add'),
        {'name': 'Fresh Org', 'slug': 'fresh-org'},
    )

    assert response.status_code == 302
    created = Organizer.objects.get(slug='fresh-org')
    core_team = created.teams.get(is_core_team=True)
    assert core_team.members.filter(pk=core_member.pk).exists()
