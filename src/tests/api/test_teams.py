import http

import pytest
from django.core import mail
from django_scopes import scopes_disabled

from pretix.base.models import Team, User


@pytest.fixture
def second_team(organizer, event):
    t = organizer.teams.create(
        name='User team',
        all_events=False,
    )
    t.limit_events.add(event)
    return t


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
    'can_view_vouchers': True,
    'can_change_vouchers': True,
    'can_checkin_orders': False,
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
    'can_view_vouchers': False,
    'can_change_vouchers': False,
    'can_checkin_orders': False,
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


# Video Permissions Tests
@pytest.mark.django_db
def test_team_video_permissions_in_api_response(token_client, organizer, event, team):
    """Test that video permission fields are included in API responses."""
    resp = token_client.get('/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, team.pk))
    assert resp.status_code == http.HTTPStatus.OK

    # Check that all video permission fields are present in the response
    video_permission_fields = [
        'can_video_create_stages',
        'can_video_create_channels',
        'can_video_direct_message',
        'can_video_manage_announcements',
        'can_video_view_users',
        'can_video_manage_users',
        'can_video_manage_rooms',
        'can_video_manage_kiosks',
        'can_video_manage_configuration',
    ]

    for field in video_permission_fields:
        assert field in resp.data, f"Field {field} not found in API response"


@pytest.mark.django_db
def test_team_create_with_video_permissions(token_client, organizer, event):
    """Test creating a team with video permissions via API."""
    payload = {
        'name': 'Video Team',
        'limit_events': ['dummy'],
        'can_video_create_stages': True,
        'can_video_create_channels': True,
        'can_video_direct_message': True,
    }

    resp = token_client.post(
        '/api/v1/organizers/{}/teams/'.format(organizer.slug),
        payload,
        format='json',
    )
    assert resp.status_code == 201

    with scopes_disabled():
        team = Team.objects.get(pk=resp.data['id'])
        assert team.can_video_create_stages
        assert team.can_video_create_channels
        assert team.can_video_direct_message
        # Fields not specified should default to False
        assert team.can_video_manage_announcements is False


@pytest.mark.django_db
def test_team_update_video_permissions(token_client, organizer, event, second_team):
    """Test updating video permissions via API."""
    assert not second_team.can_video_create_stages
    assert not second_team.can_video_manage_rooms

    resp = token_client.patch(
        '/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, second_team.pk),
        {
            'can_video_create_stages': True,
            'can_video_manage_rooms': True,
        },
        format='json',
    )
    assert resp.status_code == 200

    second_team.refresh_from_db()
    assert second_team.can_video_create_stages is True
    assert second_team.can_video_manage_rooms is True


@pytest.mark.django_db
def test_team_video_permissions_default_false(token_client, organizer, event):
    """Test that video permissions default to False when creating a team."""
    payload = {
        'name': 'Basic Team',
        'limit_events': ['dummy'],
    }

    resp = token_client.post(
        '/api/v1/organizers/{}/teams/'.format(organizer.slug),
        payload,
        format='json',
    )
    assert resp.status_code == 201

    # All video permissions should be False by default
    assert resp.data['can_video_create_stages'] is False
    assert resp.data['can_video_create_channels'] is False
    assert resp.data['can_video_direct_message'] is False
    assert resp.data['can_video_manage_announcements'] is False
    assert resp.data['can_video_view_users'] is False
    assert resp.data['can_video_manage_users'] is False
    assert resp.data['can_video_manage_rooms'] is False
    assert resp.data['can_video_manage_kiosks'] is False
    assert resp.data['can_video_manage_configuration'] is False


@pytest.mark.django_db
def test_team_partial_video_permissions_update(token_client, organizer, event, second_team):
    """Test updating only some video permissions leaves others unchanged."""
    # Set initial state
    second_team.can_video_create_stages = True
    second_team.can_video_manage_rooms = True
    second_team.save()

    # Update only one permission
    resp = token_client.patch(
        '/api/v1/organizers/{}/teams/{}/'.format(organizer.slug, second_team.pk),
        {
            'can_video_create_channels': True,
        },
        format='json',
    )
    assert resp.status_code == 200

    second_team.refresh_from_db()
    # New permission should be set
    assert second_team.can_video_create_channels is True
    # Existing permissions should be unchanged
    assert second_team.can_video_create_stages is True
    assert second_team.can_video_manage_rooms is True
    # Other permissions should still be False
    assert second_team.can_video_direct_message is False
