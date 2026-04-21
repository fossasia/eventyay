from urllib.parse import parse_qs, urlparse

import pytest
from django.http import HttpResponseRedirect
from django.urls import reverse

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject
from eventyay.plugins.socialauth.views import OAuthReturnView


@pytest.fixture
def preferred_login_providers():
    GlobalSettingsObject().settings.set(
        'login_providers',
        {
            'mediawiki': {
                'state': False,
                'client_id': '',
                'secret': '',
                'is_preferred': False,
            },
            'github': {
                'state': True,
                'client_id': 'github-client',
                'secret': 'github-secret',
                'is_preferred': True,
            },
            'google': {
                'state': True,
                'client_id': 'google-client',
                'secret': 'google-secret',
                'is_preferred': False,
            },
        },
    )


@pytest.mark.django_db
def test_preferred_provider_renders_before_email_form(client, preferred_login_providers):
    response = client.get(reverse('eventyay_common:auth.login'))

    assert response.status_code == 200
    assert response.text.index('Login with Github') < response.text.index("id='login-form'")
    assert 'login-option-primary' in response.text
    assert 'login-options-secondary-group' in response.text
    assert 'login-separator-label' in response.text
    assert 'or use the following:' not in response.text
    assert response.text.count('login-option-secondary') == 2


@pytest.mark.django_db
def test_failed_email_login_keeps_native_form_expanded(client, preferred_login_providers):
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')

    response = client.post(
        reverse('eventyay_common:auth.login'),
        data={
            'email': user.email,
            'password': 'wrong-password',
        },
    )

    assert response.status_code == 200
    assert "id='login-form'" in response.text
    assert 'This combination of credentials is not known to our system.' in response.text


@pytest.mark.django_db
def test_oauth_return_keeps_long_session_for_oauth2_handoff(client, monkeypatch):
    oauth2_params = {
        'response_type': 'code',
        'client_id': 'oauth-client',
        'redirect_uri': 'https://example.com/callback',
        'scope': 'profile',
        'state': 'expected-state',
    }
    session = client.session
    session['oauth2_params'] = oauth2_params
    session['socialauth_keep_logged_in'] = True
    session.save()

    captured = {}

    def fake_process_login_and_set_cookie(request, user, keep_logged_in):
        captured['keep_logged_in'] = keep_logged_in
        response = HttpResponseRedirect('/after-login/')
        response.set_cookie('sso_token', 'test-token')
        return response

    monkeypatch.setattr(
        'eventyay.plugins.socialauth.views.process_login_and_set_cookie',
        fake_process_login_and_set_cookie,
    )
    monkeypatch.setattr(
        'eventyay.plugins.socialauth.views.reverse',
        lambda name: '/oauth/authorize/' if name == 'eventyay_common:oauth2_provider.authorize' else reverse(name),
    )
    monkeypatch.setattr(
        OAuthReturnView,
        'get_or_create_user',
        lambda self, request: object(),
    )

    response = client.get(reverse('plugins:socialauth:social.oauth.return'))

    assert response.status_code == 302
    assert captured['keep_logged_in'] is True
    assert 'sso_token' in response.cookies
    assert 'socialauth_keep_logged_in' not in client.session

    parsed_redirect = urlparse(response['Location'])
    assert parsed_redirect.path == '/oauth/authorize/'
    assert parse_qs(parsed_redirect.query) == {key: [value] for key, value in oauth2_params.items()}
