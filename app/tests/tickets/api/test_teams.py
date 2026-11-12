from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core import mail
from django.dispatch import Signal
from django_scopes import scopes_disabled
from rest_framework.exceptions import PermissionDenied

from eventyay.api.views.team import TeamViewSet as TalkTeamViewSet
from eventyay.base.models import Team, User
from eventyay.base.models.auth import StaffSession
from eventyay.base.services.team_permissions import TEAM_DELEGATION_ERROR


@pytest.fixture
def second_team(organizer, event):
    t = organizer.teams.create(
        name='User team',
        all_events=False,
    )
    t.limit_events.add(event)
    return t


@pytest.fixture
def limited_team_token(client, organizer, monkeypatch):
    monkeypatch.setattr('eventyay.base.entitlements.entitlement_check', Signal())
    team = organizer.teams.create(name='Team managers', all_events=True, can_change_teams=True)
    token = team.tokens.create(name='Team manager token')
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.token}')
    return team


@pytest.mark.django_db
@pytest.mark.parametrize('method', ['post', 'patch'])
@pytest.mark.parametrize('permission', ['can_change_orders', 'can_manage_bank_transfers', 'can_manage_gift_cards'])
def test_team_token_cannot_grant_extra_permissions(client, organizer, limited_team_token, method, permission):
    base_url = f'/api/v1/organizers/{organizer.slug}/teams/'
    data = {permission: True}
    if method == 'post':
        response = client.post(
            base_url, {'name': 'Finance', 'limit_events': [], 'all_events': True, **data}, format='json'
        )
    else:
        response = client.patch(f'{base_url}{limited_team_token.pk}/', data, format='json')

    assert response.status_code == 403
    assert str(response.data['detail']) == str(TEAM_DELEGATION_ERROR)
    limited_team_token.refresh_from_db()
    assert limited_team_token.permission_set() == {'can_change_teams'}
    assert organizer.teams.count() == 1


@pytest.mark.django_db
def test_team_token_can_update_without_expanding_existing_grants(client, organizer, event, limited_team_token):
    finance = organizer.teams.create(name='Finance', can_manage_bank_transfers=True)
    finance.limit_events.add(event)
    url = f'/api/v1/organizers/{organizer.slug}/teams/{finance.pk}/'

    response = client.patch(url, {'name': 'Banking'}, format='json')

    assert response.status_code == 200
    finance.refresh_from_db()
    assert finance.name == 'Banking'
    assert finance.permission_set() == {'can_manage_bank_transfers', 'can_view_orders'}

    response = client.patch(url, {'all_events': True, 'limit_events': []}, format='json')

    assert response.status_code == 403
    finance.refresh_from_db()
    assert not finance.all_events
    assert list(finance.limit_events.all()) == [event]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('resource', 'data'),
    [
        ('invites', {'email': 'invitee@example.com'}),
        ('tokens', {'name': 'New token'}),
    ],
)
def test_team_token_cannot_delegate_privileged_team(client, organizer, limited_team_token, resource, data):
    team = organizer.teams.create(name='Finance', all_events=True, can_manage_gift_cards=True)

    response = client.post(f'/api/v1/organizers/{organizer.slug}/teams/{team.pk}/{resource}/', data, format='json')

    assert response.status_code == 403
    assert str(response.data['detail']) == str(TEAM_DELEGATION_ERROR)
    assert not team.invites.exists()
    assert not team.tokens.exists()


@pytest.mark.django_db
def test_event_limited_team_token_cannot_mint_all_events_token(client, organizer, event, limited_team_token):
    limited_team_token.all_events = False
    limited_team_token.save(update_fields=['all_events'])
    limited_team_token.limit_events.add(event)
    team = organizer.teams.create(name='All-event managers', all_events=True, can_change_teams=True)

    response = client.post(
        f'/api/v1/organizers/{organizer.slug}/teams/{team.pk}/tokens/', {'name': 'Wider token'}, format='json'
    )

    assert response.status_code == 403
    assert str(response.data['detail']) == str(TEAM_DELEGATION_ERROR)
    assert not team.tokens.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('method', ['perform_create', 'perform_update'])
def test_talk_team_view_checks_delegation(organizer, limited_team_token, method):
    view = TalkTeamViewSet()
    view.request = SimpleNamespace(
        organizer=organizer, auth=limited_team_token.tokens.get(), session=SimpleNamespace(session_key=None)
    )
    serializer = Mock(instance=limited_team_token, validated_data={'is_reviewer': True})

    with pytest.raises(PermissionDenied, match=str(TEAM_DELEGATION_ERROR)):
        getattr(view, method)(serializer)

    serializer.save.assert_not_called()


@pytest.mark.django_db
def test_active_staff_session_can_invite_through_team_api(client, organizer):
    staff = User.objects.create_user('staff@example.com', is_staff=True)
    client.force_login(staff)
    StaffSession.objects.create(user=staff, session_key=client.session.session_key)
    team = organizer.teams.create(name='Finance', all_events=True, can_manage_gift_cards=True)

    response = client.post(
        f'/api/v1/organizers/{organizer.slug}/teams/{team.pk}/invites/', {'email': 'invitee@example.com'}, format='json'
    )

    assert response.status_code == 201
    assert team.invites.get().invited_by == staff


TEST_TEAM_RES = {
    'id': 1,
    'name': 'Test-Team',
    'all_events': True,
    'limit_events': [],
    'can_create_events': True,
    'can_change_teams': True,
    'can_change_organizer_settings': True,
    'can_manage_gift_cards': True,
    'can_change_event_settings': True,
    'can_change_items': True,
    'can_view_orders': True,
    'can_change_orders': True,
    'can_manage_bank_transfers': False,
    'can_view_vouchers': True,
    'can_change_vouchers': True,
    'can_checkin_orders': False,
    'can_change_exhibition_proposals': False,
    'is_exhibition_reviewer': False,
    'hide_exhibition_applicant_emails': False,
}

SECOND_TEAM_RES = {
    'id': 1,
    'name': 'User team',
    'all_events': False,
    'limit_events': ['dummy'],
    'can_create_events': False,
    'can_change_teams': False,
    'can_change_organizer_settings': False,
    'can_manage_gift_cards': False,
    'can_change_event_settings': False,
    'can_change_items': False,
    'can_view_orders': False,
    'can_change_orders': False,
    'can_manage_bank_transfers': False,
    'can_view_vouchers': False,
    'can_change_vouchers': False,
    'can_checkin_orders': False,
    'can_change_exhibition_proposals': False,
    'is_exhibition_reviewer': False,
    'hide_exhibition_applicant_emails': False,
}


@pytest.mark.django_db
def test_team_list(token_client, organizer, event, team):
    res = dict(TEST_TEAM_RES)
    res['id'] = team.pk

    resp = token_client.get('/api/v1/organizers/{}/teams/'.format(organizer.slug))
    assert resp.status_code == 200
    assert [res] == resp.data['results']


@pytest.mark.django_db
def test_team_detail(token_client, organizer, event, second_team):
    res = dict(SECOND_TEAM_RES)
    res['id'] = second_team.pk
    resp = token_client.get('/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, second_team.pk))
    assert resp.status_code == 200
    assert res == resp.data


TEST_TEAM_CREATE_PAYLOAD = {
    'name': 'Foobar',
    'limit_events': ['dummy'],
}


@pytest.mark.django_db
def test_team_create(token_client, organizer, event):
    resp = token_client.post(
        '/api/v1/organizers/{}/teams/'.format(organizer.slug),
        TEST_TEAM_CREATE_PAYLOAD,
        format='json',
    )
    assert resp.status_code == 201
    with scopes_disabled():
        team = Team.objects.get(pk=resp.data['id'])
        assert list(team.limit_events.all()) == [event]


@pytest.mark.django_db
def test_team_update(token_client, organizer, event, second_team):
    assert not second_team.can_change_event_settings
    resp = token_client.patch(
        '/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, second_team.pk),
        {
            'can_change_event_settings': True,
        },
        format='json',
    )
    assert resp.status_code == 200
    second_team.refresh_from_db()
    assert second_team.can_change_event_settings

    resp = token_client.patch(
        '/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, second_team.pk),
        {
            'all_events': True,
        },
        format='json',
    )
    print(resp.data)
    assert resp.status_code == 400


@pytest.mark.django_db
def test_team_update_enforces_permission_implications(token_client, organizer, event, second_team):
    resp = token_client.patch(
        '/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, second_team.pk),
        {
            'can_change_orders': True,
            'can_view_orders': False,
            'can_change_vouchers': True,
            'can_view_vouchers': False,
            'can_manage_bank_transfers': True,
        },
        format='json',
    )
    assert resp.status_code == 200
    second_team.refresh_from_db()
    assert second_team.can_view_orders
    assert second_team.can_view_vouchers


@pytest.mark.django_db
def test_team_delete(token_client, organizer, event, second_team):
    resp = token_client.delete(
        '/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, second_team.pk),
        format='json',
    )
    assert resp.status_code == 204
    assert organizer.teams.count() == 1


TEST_TEAM_MEMBER_RES = {
    'email': 'dummy@dummy.dummy',
    'fullname': None,
    'require_2fa': False,
}


@pytest.mark.django_db
def test_team_members_list(token_client, organizer, event, user, team):
    team.members.add(user)
    res = dict(TEST_TEAM_MEMBER_RES)
    res['id'] = user.pk

    resp = token_client.get('/api/v1/organizers/{}/teams/{}/members/'.format(organizer.slug, team.pk))
    assert resp.status_code == 200
    assert [res] == resp.data['results']


@pytest.mark.django_db
def test_team_members_detail(token_client, organizer, event, team, user):
    team.members.add(user)
    res = dict(TEST_TEAM_MEMBER_RES)
    res['id'] = user.pk
    resp = token_client.get('/api/v1/organizers/{}/teams/{}/members/{}/'.format(organizer.slug, team.pk, user.pk))
    assert resp.status_code == 200
    assert res == resp.data


@pytest.mark.django_db
def test_team_members_delete(token_client, organizer, event, team, user):
    team.members.add(user)
    resp = token_client.delete('/api/v1/organizers/{}/teams/{}/members/{}/'.format(organizer.slug, team.pk, user.pk))
    assert resp.status_code == 204
    assert team.members.count() == 0
    assert User.objects.filter(pk=user.pk).exists()


@pytest.fixture
def invite(team):
    return team.invites.create(email='foo@bar.com')


TEST_TEAM_INVITE_RES = {
    'email': 'foo@bar.com',
}


@pytest.mark.django_db
def test_team_invites_list(token_client, organizer, event, user, team, invite):
    res = dict(TEST_TEAM_INVITE_RES)
    res['id'] = invite.pk

    resp = token_client.get('/api/v1/organizers/{}/teams/{}/invites/'.format(organizer.slug, team.pk))
    assert resp.status_code == 200
    assert [res] == resp.data['results']


@pytest.mark.django_db
def test_team_invites_detail(token_client, organizer, event, team, user, invite):
    res = dict(TEST_TEAM_INVITE_RES)
    res['id'] = invite.pk
    resp = token_client.get('/api/v1/organizers/{}/teams/{}/invites/{}/'.format(organizer.slug, team.pk, invite.pk))
    assert resp.status_code == 200
    assert res == resp.data


@pytest.mark.django_db
def test_team_invites_delete(token_client, organizer, event, team, user, invite):
    resp = token_client.delete('/api/v1/organizers/{}/teams/{}/invites/{}/'.format(organizer.slug, team.pk, invite.pk))
    assert resp.status_code == 204
    assert team.invites.count() == 0


@pytest.mark.django_db
def test_team_invites_create(token_client, organizer, event, team, user):
    resp = token_client.post(
        '/api/v1/organizers/{}/teams/{}/invites/'.format(organizer.slug, team.pk),
        {'email': 'newmail@dummy.dummy'},
    )
    assert resp.status_code == 201
    assert team.invites.get().email == 'newmail@dummy.dummy'
    assert len(mail.outbox) == 1

    resp = token_client.post(
        '/api/v1/organizers/{}/teams/{}/invites/'.format(organizer.slug, team.pk),
        {'email': 'newmail@dummy.dummy'},
    )
    assert resp.status_code == 400
    assert resp.content.decode() == '["This user already has been invited for this team."]'

    resp = token_client.post(
        '/api/v1/organizers/{}/teams/{}/invites/'.format(organizer.slug, team.pk),
        {'email': user.email},
    )
    assert resp.status_code == 201
    assert not resp.data.get('id')
    assert team.invites.count() == 1
    assert user in team.members.all()

    resp = token_client.post(
        '/api/v1/organizers/{}/teams/{}/invites/'.format(organizer.slug, team.pk),
        {'email': user.email},
    )
    assert resp.status_code == 400
    assert resp.content.decode() == '["This user already has permissions for this team."]'


TEST_TEAM_TOKEN_RES = {
    'name': 'Testtoken',
    'active': True,
}


@pytest.fixture
def token(second_team):
    t = second_team.tokens.create(name='Testtoken')
    return t


@pytest.mark.django_db
def test_team_tokens_list(token_client, organizer, event, user, second_team, token):
    res = dict(TEST_TEAM_TOKEN_RES)
    res['id'] = token.pk

    resp = token_client.get('/api/v1/organizers/{}/teams/{}/tokens/'.format(organizer.slug, second_team.pk))
    assert resp.status_code == 200
    assert [res] == resp.data['results']


@pytest.mark.django_db
def test_team_tokens_detail(token_client, organizer, event, second_team, token):
    res = dict(TEST_TEAM_TOKEN_RES)
    res['id'] = token.pk
    resp = token_client.get(
        '/api/v1/organizers/{}/teams/{}/tokens/{}/'.format(organizer.slug, second_team.pk, token.pk)
    )
    assert resp.status_code == 200
    assert res == resp.data


@pytest.mark.django_db
def test_team_tokens_delete(token_client, organizer, event, second_team, token):
    resp = token_client.delete(
        '/api/v1/organizers/{}/teams/{}/tokens/{}/'.format(organizer.slug, second_team.pk, token.pk)
    )
    assert resp.status_code == 200
    token.refresh_from_db()
    assert not token.active


@pytest.mark.django_db
def test_team_token_create(token_client, organizer, event, second_team):
    resp = token_client.post(
        '/api/v1/organizers/{}/teams/{}/tokens/'.format(organizer.slug, second_team.pk),
        {'name': 'New token'},
    )
    assert resp.status_code == 201
    t = second_team.tokens.get()
    assert t.name == 'New token'
    assert t.active
    assert resp.data['token'] == t.token


@pytest.mark.django_db
def test_team_permission_error_is_raised(organizer):
    from eventyay.base.models.organizer import TeamPermissionError, check_access_permissions

    organizer.teams.all().delete()
    with pytest.raises(TeamPermissionError):
        check_access_permissions(organizer)

