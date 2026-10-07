"""Regression tests for the authorized applications account page.

The list template reversed 'eventyay_common:account.oauth.own-app.revoke',
which is not a registered URL name, so rendering raised NoReverseMatch. It went
unnoticed because that <a> sits inside {% if tokens %}, meaning the page only
broke for users who actually had an authorized application.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.api.models import OAuthAccessToken, OAuthApplication
from eventyay.base.models import User

pytestmark = pytest.mark.django_db

LIST_URL = 'eventyay_common:account.oauth.authorized-apps'
REVOKE_URL = 'eventyay_common:account.oauth.authorized-app.revoke'


@pytest.fixture
def application():
    return OAuthApplication.objects.create(
        name='repro-app',
        redirect_uris='https://example.org/callback',
        client_type='confidential',
        authorization_grant_type='authorization-code',
    )


@pytest.fixture
def token(user, application):
    return OAuthAccessToken.objects.create(
        user=user,
        application=application,
        token='test-access-token',
        scope='read',
        expires=now() + timedelta(hours=1),
    )


def test_authorized_apps_page_renders_when_user_has_a_token(authenticated_client, token):
    resp = authenticated_client.get(reverse(LIST_URL))
    assert resp.status_code == 200
    assert token.application.name in resp.content.decode()


def test_revoke_url_reverses(token):
    assert reverse(REVOKE_URL, kwargs={'pk': token.pk}) == (
        f'/common/account/oauth/authorized-app/{token.pk}/revoke'
    )


def test_revoke_confirm_page_interpolates_application_name(authenticated_client, application, token):
    resp = authenticated_client.get(reverse(REVOKE_URL, kwargs={'pk': token.pk}))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert application.name in body
    assert '%(application)s' not in body


def test_revoke_post_deletes_the_token(authenticated_client, token):
    resp = authenticated_client.post(reverse(REVOKE_URL, kwargs={'pk': token.pk}))
    assert resp.status_code == 302
    assert resp['Location'] == reverse(LIST_URL)
    assert not OAuthAccessToken.objects.filter(pk=token.pk).exists()


def test_user_cannot_revoke_another_users_token(client, token):
    other = User.objects.create_user(email='other@example.com', password='password123')
    client.force_login(other)
    resp = client.get(reverse(REVOKE_URL, kwargs={'pk': token.pk}))
    assert resp.status_code == 404