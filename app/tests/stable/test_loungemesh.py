from datetime import timedelta

import jwt
import pytest
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Room
from eventyay.base.models.auth import StaffSession
from eventyay.base.models.loungemesh import LoungeMeshAccessToken
from eventyay.base.services.loungemesh import (
    issue_join_url,
    issue_jitsi_jwt,
    issue_opaque_token,
    loungemesh_embed_origins,
    loungemesh_permissions_policy,
    sanitize_loungemesh_config,
    token_exchange_payload,
    verify_loungemesh_token,
)
from eventyay.base.settings import GlobalSettingsObject


def _enable_loungemesh(*, features=None):
    gs = GlobalSettingsObject().settings
    gs.set('loungemesh_enabled', True)
    gs.set('loungemesh_url', 'https://loungemesh.com')
    gs.set('loungemesh_jitsi_app_id', 'testapp')
    gs.set('loungemesh_jitsi_app_secret', 'testsecret')
    gs.set(
        'loungemesh_organizer_features',
        features if features is not None else ['notes', 'whiteboard', 'poll'],
    )


@pytest.mark.django_db
def test_sanitize_strips_disallowed_features():
    _enable_loungemesh(features=['notes'])
    cleaned = sanitize_loungemesh_config(
        {'features': {'notes': True, 'whiteboard': True, 'poll': True}}
    )
    assert cleaned['features']['notes'] is True
    assert cleaned['features']['whiteboard'] is False
    assert cleaned['features']['poll'] is False


@pytest.mark.django_db
def test_sanitize_drops_non_http_url_override():
    _enable_loungemesh(features=['notes'])
    cleaned = sanitize_loungemesh_config(
        {'url': 'javascript:alert(1)', 'features': {'notes': True}}
    )
    assert 'url' not in cleaned
    cleaned_http = sanitize_loungemesh_config(
        {'url': 'https://loungemesh.example/app', 'features': {'notes': True}}
    )
    assert cleaned_http['url'] == 'https://loungemesh.example/app'


@pytest.mark.django_db
def test_issue_and_exchange_token(event, user):
    _enable_loungemesh()
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Lounge',
            module_config=[
                {
                    'type': 'call.loungemesh',
                    'config': {'features': {'notes': True, 'whiteboard': True}},
                }
            ],
        )
        user.profile = {'display_name': 'Ada'}
        user.save()
        token = issue_opaque_token(event, room, user, moderator=True)
        url = issue_join_url(event, room, user, moderator=False)

    assert token.token
    assert 'https://loungemesh.com/join/lms-testevent-' in url
    assert f'token={token.token}' not in url  # a new token is minted for join URL
    access = verify_loungemesh_token(token.token)
    assert access is not None
    payload = token_exchange_payload(access)
    assert payload['display_name'] == 'Ada'
    assert payload['moderator'] is True
    assert payload['features']['notes'] is True
    assert payload['features']['whiteboard'] is True
    assert payload['features']['poll'] is False
    decoded = jwt.decode(payload['jwt'], 'testsecret', algorithms=['HS256'])
    assert decoded['context']['user']['moderator'] is True
    assert decoded['room'].startswith('lms-testevent-')


@pytest.mark.django_db
def test_expired_token_is_rejected(event, user):
    _enable_loungemesh()
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Lounge',
            module_config=[{'type': 'call.loungemesh', 'config': {}}],
        )
        token = LoungeMeshAccessToken.objects.create(
            event=event,
            room=room,
            user=user,
            expires=now() - timedelta(minutes=1),
        )
    assert verify_loungemesh_token(token.token) is None


@pytest.mark.django_db
def test_token_api_exchange(event, user, client):
    _enable_loungemesh()
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Lounge',
            module_config=[
                {'type': 'call.loungemesh', 'config': {'features': {'notes': True}}}
            ],
        )
        token = issue_opaque_token(event, room, user, moderator=False)
    response = client.post(
        '/api/v1/loungemesh/token/',
        {'token': token.token},
        content_type='application/json',
    )
    assert response.status_code == 200
    body = response.json()
    assert body['jitsi_room'] == f'lms-testevent-{room.pk}'
    assert body['features']['notes'] is True


@pytest.mark.django_db
def test_token_api_rejects_invalid(client):
    response = client.post(
        '/api/v1/loungemesh/token/',
        {'token': 'nope'},
        content_type='application/json',
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_join_url_fails_when_disabled(event, user):
    gs = GlobalSettingsObject().settings
    gs.set('loungemesh_enabled', False)
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name='Lounge',
            module_config=[{'type': 'call.loungemesh', 'config': {}}],
        )
        assert issue_join_url(event, room, user, moderator=False) is None


@pytest.mark.django_db
def test_video_admin_loungemesh_settings(staff_client, staff_user):
    StaffSession.objects.create(
        user=staff_user,
        session_key=staff_client.session.session_key,
    )
    url = reverse('eventyay_admin:video_admin:loungemesh.settings')
    get_response = staff_client.get(url)
    assert get_response.status_code == 200
    post_response = staff_client.post(
        url,
        {
            'enabled': 'on',
            'url': 'https://loungemesh.example',
            'jitsi_app_id': 'app',
            'jitsi_app_secret': 'secret',
            'organizer_features': ['notes', 'chat'],
        },
    )
    assert post_response.status_code == 302
    gs = GlobalSettingsObject().settings
    assert gs.get('loungemesh_enabled') is True
    assert gs.get('loungemesh_url') == 'https://loungemesh.example'
    assert list(gs.get('loungemesh_organizer_features')) == ['notes', 'chat']


@pytest.mark.django_db
def test_jitsi_jwt_omits_secret_when_unconfigured():
    gs = GlobalSettingsObject().settings
    gs.set('loungemesh_jitsi_app_id', '')
    gs.set('loungemesh_jitsi_app_secret', '')
    assert (
        issue_jitsi_jwt(
            display_name='Ada',
            jitsi_room='lms-x-1',
            moderator=False,
            features={},
        )
        is None
    )


def test_permissions_policy_uses_provided_origins():
    policy = loungemesh_permissions_policy(('https://loungemesh.com',))
    assert 'camera=(self "https://loungemesh.com")' in policy
    assert 'microphone=(self "https://loungemesh.com")' in policy


@pytest.mark.django_db
def test_embed_origins_include_configured_url():
    gs = GlobalSettingsObject().settings
    gs.set('loungemesh_url', 'http://localhost:5173')
    origins = loungemesh_embed_origins()
    assert 'https://loungemesh.com' in origins
    assert 'http://localhost:5173' in origins
    policy = loungemesh_permissions_policy()
    assert 'camera=(self' in policy
    assert '"https://loungemesh.com"' in policy
    assert '"http://localhost:5173"' in policy
