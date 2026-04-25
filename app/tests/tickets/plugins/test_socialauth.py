import re
from urllib.parse import parse_qs, urlparse

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.mediawiki.provider import MediaWikiProvider
from django.http import HttpResponseRedirect
from django.test.client import RequestFactory
from django.urls import reverse

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject
from eventyay.plugins.socialauth.adapter import CustomSocialAccountAdapter
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
    match = re.search(r"id=['\"]login-form['\"]\s+class=['\"]([^'\"]*)['\"]", response.text)
    assert match is not None
    classes = match.group(1).split()
    assert 'collapse' not in classes or 'in' in classes
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


@pytest.mark.django_db
def test_mediawiki_oauth_links_existing_user_even_if_app_disables_email_authentication():
    user = User.objects.create_user('existing-mediawiki@example.com', 'dummy')

    request = RequestFactory().get('/accounts/mediawiki/login/callback/')
    app = SocialApp(
        provider='mediawiki',
        name='mediawiki-app',
        client_id='client-id',
        secret='client-secret',
        settings={'email_authentication': False},
    )
    provider = MediaWikiProvider(request=request, app=app)

    social_login = provider.sociallogin_from_response(
        request,
        {
            'sub': '12345',
            'email': user.email,
            'confirmed_email': True,
            'username': 'ExampleUser',
            'realname': 'Example User',
        },
    )

    social_login.lookup()

    assert social_login.is_existing
    assert social_login.user == user


@pytest.mark.django_db
def test_mediawiki_oauth_pre_social_login_links_existing_user_from_profile_email(monkeypatch):
    user = User.objects.create_user('existing-mediawiki-profile@example.com', 'dummy')

    request = RequestFactory().get('/accounts/mediawiki/login/callback/')
    app = SocialApp.objects.create(
        provider='mediawiki',
        name='mediawiki-app',
        client_id='client-id',
        secret='client-secret',
    )
    provider = MediaWikiProvider(request=request, app=app)

    social_login = provider.sociallogin_from_response(
        request,
        {
            'sub': '12345',
            'email': user.email,
            'confirmed_email': False,
            'username': 'ExampleUser',
            'realname': 'Example User',
        },
    )
    social_login.lookup()

    assert not social_login.is_existing

    monkeypatch.setattr(
        CustomSocialAccountAdapter,
        'fetch_mediawiki_profile_email',
        lambda self, login: user.email,
    )

    adapter = CustomSocialAccountAdapter(request)
    adapter.pre_social_login(request, social_login)

    assert social_login.is_existing
    assert social_login.user == user
    assert social_login._did_authenticate_by_email == user.email


@pytest.mark.django_db
def test_mediawiki_signup_form_links_existing_user_without_assertion(client):
    user = User.objects.create_user('existing-mediawiki-signup@example.com', 'dummy')
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)

    request = RequestFactory().get('/accounts/mediawiki/login/callback/')
    app = SocialApp.objects.create(
        provider='mediawiki',
        name='mediawiki-app',
        client_id='client-id',
        secret='client-secret',
    )
    provider = MediaWikiProvider(request=request, app=app)
    social_login = provider.sociallogin_from_response(
        request,
        {
            'sub': '12345',
            'email': user.email,
            'confirmed_email': False,
            'username': 'ExampleUser',
            'realname': 'Example User',
        },
    )
    social_login.state = {'process': 'login'}

    session = client.session
    session['socialaccount_sociallogin'] = social_login.serialize()
    session.save()

    response = client.post(
        reverse('socialaccount_signup'),
        data={'email': user.email},
    )

    assert response.status_code == 302
    assert client.session.get('_auth_user_id') == str(user.pk)
    assert SocialAccount.objects.filter(user=user, provider='mediawiki').exists()
