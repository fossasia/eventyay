import importlib

import pytest
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from rest_framework.test import APIClient

from eventyay.base.models import Event, Organizer, Team, TeamInvite, User
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.organizer import TeamAPIToken, TeamPermissionError
from eventyay.base.services.organizer_creation import (
    can_manage_team_members,
    create_core_team,
    is_event_core_team_member,
    removes_last_active_core_member,
)
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
def test_core_team_permissions_are_permanent(organizer, core_team):
    assert all(getattr(core_team, field) for field in Team._permission_field_names())
    core_team.all_events = core_team.can_view_event_info = False
    core_team.save()
    core_team.refresh_from_db()
    assert core_team.all_events and core_team.can_view_event_info
    for form_type in (ControlTeamForm, TalkTeamForm):
        form = form_type(instance=core_team, organizer=organizer)
        assert all(field.disabled for name, field in form.fields.items() if name != 'name')
    with pytest.raises(TeamPermissionError):
        core_team.delete()
    core_team.is_core_team = False
    with pytest.raises(TeamPermissionError):
        core_team.save()


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


@pytest.fixture
def manager(organizer):
    """A team manager who is not in the core team."""
    user = User.objects.create_user('manager@example.com', 'manager')
    team = Team.objects.create(organizer=organizer, name='Managers', all_events=True, can_change_teams=True)
    team.members.add(user)
    return user


@pytest.mark.django_db
def test_any_actor_may_manage_members_of_ordinary_teams(organizer, manager):
    ordinary = Team.objects.create(organizer=organizer, name='Helpers')
    assert can_manage_team_members(ordinary, user=manager)
    assert can_manage_team_members(ordinary)


@pytest.mark.django_db
def test_only_the_core_side_may_manage_core_team_members(core_team, owner, manager, organizer):
    token = TeamAPIToken.objects.create(team=core_team, name='Core token')
    other_token = TeamAPIToken.objects.create(
        team=Team.objects.get(organizer=organizer, name='Managers'), name='Manager token'
    )
    assert can_manage_team_members(core_team, user=owner)
    assert can_manage_team_members(core_team, token=token)
    assert not can_manage_team_members(core_team, user=manager)
    assert not can_manage_team_members(core_team, token=other_token)
    assert not can_manage_team_members(core_team, user=AnonymousUser())
    assert not can_manage_team_members(core_team)


@pytest.mark.django_db
def test_inactive_core_member_and_foreign_core_token_may_not_manage(core_team, owner):
    foreign = Organizer.objects.create(name='Foreign', slug='foreign')
    foreign_token = TeamAPIToken.objects.create(team=create_core_team(foreign, owner), name='Foreign token')
    assert not can_manage_team_members(core_team, token=foreign_token)
    owner.is_active = False
    owner.save()
    assert not can_manage_team_members(core_team, user=owner)


@pytest.mark.django_db
def test_staff_session_may_manage_core_team_members(core_team):
    staff = User.objects.create_user('staff-admin@example.com', 'x', is_staff=True)
    assert not can_manage_team_members(core_team, user=staff, session_key='abc')
    StaffSession.objects.create(user=staff, date_start=now(), session_key='abc')
    staff = User.objects.get(pk=staff.pk)  # the staff session lookup is cached per user object
    assert can_manage_team_members(core_team, user=staff, session_key='abc')
    assert not can_manage_team_members(core_team, user=staff, session_key='other')


def invite_post(team, email, **extra):
    return {'team_action': 'members', 'team_id': team.pk, f'team-{team.pk}-invite-user': email, **extra}


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_manager_cannot_invite_themselves_into_core_team_on_organizer_page(
    client, core_team, manager, organizer, event
):
    client.force_login(manager)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    response = client.post(url, invite_post(core_team, manager.email), follow=True)
    assert 'Only members of the Core Organizing Team' in response.content.decode()
    assert not TeamInvite.all_objects.filter(team=core_team).exists()
    assert not is_event_core_team_member(manager, event)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_manager_cannot_change_core_team_members_on_organizer_page(client, core_team, owner, manager, organizer):
    pending = core_team.invites.create(email='pending@example.com')
    client.force_login(manager)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    base = {'team_action': 'members', 'team_id': core_team.pk}
    for action in (
        {'remove-member': owner.pk},
        {'remove-invite': pending.pk},
        {'resend-invite': pending.pk},
    ):
        response = client.post(url, {**base, **action}, follow=True)
        assert 'Only members of the Core Organizing Team' in response.content.decode()
    assert list(core_team.members.all()) == [owner]
    assert TeamInvite.all_objects.filter(pk=pending.pk).exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_core_member_can_invite_into_core_team_on_organizer_page(client, core_team, owner, organizer):
    client.force_login(owner)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    client.post(url, invite_post(core_team, 'new-owner@example.com'), follow=True)
    assert TeamInvite.all_objects.filter(team=core_team, email='new-owner@example.com').exists()


@pytest.mark.django_db
def test_organizer_api_refuses_core_team_member_changes_by_non_core_token(
    core_team, owner, manager, organizer, allow_all_entitlements
):
    manager_team = Team.objects.get(organizer=organizer, name='Managers')
    token = TeamAPIToken.objects.create(team=manager_team, name='Manager token')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.token)
    base = f'/api/v1/organizers/{organizer.slug}/teams/{core_team.pk}'

    assert client.post(f'{base}/invites/', {'email': manager.email}).status_code == 403
    assert client.delete(f'{base}/members/{owner.pk}/').status_code == 403
    assert not TeamInvite.all_objects.filter(team=core_team).exists()
    assert list(core_team.members.all()) == [owner]


@pytest.mark.django_db
def test_organizer_api_lets_core_team_token_invite_into_core_team(
    core_team, organizer, allow_all_entitlements, django_capture_on_commit_callbacks
):
    token = TeamAPIToken.objects.create(team=core_team, name='Core token')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.token)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f'/api/v1/organizers/{organizer.slug}/teams/{core_team.pk}/invites/', {'email': 'new-owner@example.com'}
        )
    assert response.status_code == 201
    assert TeamInvite.all_objects.filter(team=core_team, email='new-owner@example.com').exists()


@pytest.mark.django_db
def test_invites_to_ordinary_teams_are_not_restricted(
    organizer, manager, allow_all_entitlements, django_capture_on_commit_callbacks
):
    ordinary = Team.objects.create(organizer=organizer, name='Helpers')
    manager_team = Team.objects.get(organizer=organizer, name='Managers')
    token = TeamAPIToken.objects.create(team=manager_team, name='Manager token')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.token)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f'/api/v1/organizers/{organizer.slug}/teams/{ordinary.pk}/invites/', {'email': 'helper@example.com'}
        )
    assert response.status_code == 201


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_manager_cannot_create_or_revoke_core_team_tokens_on_organizer_page(client, core_team, manager, organizer):
    existing = core_team.tokens.create(name='Existing')
    client.force_login(manager)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    base = {'team_action': 'tokens', 'team_id': core_team.pk}
    for data in ({f'team-{core_team.pk}-token-name': 'Escalation'}, {'remove-token': existing.pk}):
        response = client.post(url, {**base, **data}, follow=True)
        assert 'Only members of the Core Organizing Team' in response.content.decode()
    assert list(core_team.tokens.values_list('name', 'active')) == [('Existing', True)]


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_core_member_can_create_core_team_tokens_on_organizer_page(client, core_team, owner, organizer):
    client.force_login(owner)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    client.post(
        url,
        {'team_action': 'tokens', 'team_id': core_team.pk, f'team-{core_team.pk}-token-name': 'Automation'},
        follow=True,
    )
    assert list(core_team.tokens.values_list('name', flat=True)) == ['Automation']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_manager_cannot_manage_core_team_tokens_on_event_api_page(client, core_team, manager, organizer, event):
    existing = core_team.tokens.create(name='Existing')
    client.force_login(manager)
    url = reverse('eventyay_common:event.api', kwargs={'organizer': organizer.slug, 'event': event.slug})
    for data in (
        {'token_action': 'create', 'team_id': core_team.pk, f'token-{core_team.pk}-name': 'Escalation'},
        {'token_action': 'revoke', 'team_id': core_team.pk, 'token_id': existing.pk},
    ):
        response = client.post(url, data, follow=True)
        assert 'Only members of the Core Organizing Team' in response.content.decode()
    assert list(core_team.tokens.values_list('name', 'active')) == [('Existing', True)]


@pytest.mark.django_db
def test_organizer_api_refuses_core_team_token_changes_by_non_core_token(
    core_team, manager, organizer, allow_all_entitlements
):
    manager_team = Team.objects.get(organizer=organizer, name='Managers')
    existing = core_team.tokens.create(name='Existing')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + TeamAPIToken.objects.create(team=manager_team, name='M').token)
    base = f'/api/v1/organizers/{organizer.slug}/teams/{core_team.pk}/tokens/'

    assert client.post(base, {'name': 'Escalation'}).status_code == 403
    assert client.delete(f'{base}{existing.pk}/').status_code == 403
    assert list(core_team.tokens.values_list('name', 'active')) == [('Existing', True)]


@pytest.mark.django_db
def test_core_team_token_can_create_core_team_tokens_through_the_api(core_team, organizer, allow_all_entitlements):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + TeamAPIToken.objects.create(team=core_team, name='Core').token)
    response = client.post(f'/api/v1/organizers/{organizer.slug}/teams/{core_team.pk}/tokens/', {'name': 'Second'})
    assert response.status_code == 201
    assert core_team.tokens.filter(name='Second').exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_last_active_core_member_cannot_remove_themselves_on_organizer_page(
    client, core_team, owner, manager, organizer
):
    client.force_login(owner)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    response = client.post(
        url, {'team_action': 'members', 'team_id': core_team.pk, 'remove-member': owner.pk}, follow=True
    )
    assert 'cannot remove the last active member of the Core Organizing Team' in response.content.decode()
    assert list(core_team.members.all()) == [owner]


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_core_member_can_be_removed_while_another_active_member_remains(client, core_team, owner, organizer):
    second = User.objects.create_user('second-owner@example.com', 'x')
    core_team.members.add(second)
    client.force_login(owner)
    url = reverse('eventyay_common:organizer.teams', kwargs={'organizer': organizer.slug})
    client.post(url, {'team_action': 'members', 'team_id': core_team.pk, 'remove-member': second.pk}, follow=True)
    assert list(core_team.members.all()) == [owner]


@pytest.mark.django_db
def test_inactive_core_members_do_not_count_as_remaining(core_team, owner):
    inactive = User.objects.create_user('inactive-owner@example.com', 'x')
    inactive.is_active = False
    inactive.save()
    core_team.members.add(inactive)
    assert removes_last_active_core_member(core_team, owner)
    assert not removes_last_active_core_member(core_team, inactive)
    ordinary = Team.objects.create(organizer=core_team.organizer, name='Helpers')
    ordinary.members.add(owner)
    assert not removes_last_active_core_member(ordinary, owner)


@pytest.mark.django_db
def test_organizer_api_keeps_the_last_active_core_member(core_team, owner, organizer, allow_all_entitlements):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + TeamAPIToken.objects.create(team=core_team, name='Core').token)
    response = client.delete(f'/api/v1/organizers/{organizer.slug}/teams/{core_team.pk}/members/{owner.pk}/')
    assert response.status_code == 400
    assert 'last active member' in str(response.data)
    assert list(core_team.members.all()) == [owner]


@pytest.mark.django_db
def test_core_team_api_protects_permissions_and_deletion(core_team, organizer, allow_all_entitlements):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION='Token ' + TeamAPIToken.objects.create(team=core_team, name='Core').token)
    url = f'/api/v1/organizers/{organizer.slug}/teams/{core_team.pk}/'
    assert client.patch(url, {'name': 'Organizers'}, format='json').status_code == 200
    assert client.patch(url, {'can_view_orders': False}, format='json').status_code == 400
    assert client.delete(url).status_code == 403
    core_team.refresh_from_db()
    assert core_team.can_view_orders


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_owner_cannot_delete_core_team_with_another_manager(client, core_team, owner, manager):
    client.force_login(owner)
    url = reverse('eventyay_common:organizer.team.delete', kwargs={
        'organizer': core_team.organizer.slug, 'team': core_team.pk,
    })
    assert client.get(url).context['possible'] is False
    assert client.post(url).status_code == 302
    assert Team.objects.filter(pk=core_team.pk).exists()
