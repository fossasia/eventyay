import re
import time as import_time
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.consts import KEY_LAST_FORCE_LOGIN, KEY_LONG_SESSION, KEY_SOCIAL_KEEP_LOGGED_IN
from eventyay.eventyay_common.adapter import CustomAccountAdapter
from eventyay.plugins.socialauth.adapter import CustomSocialAccountAdapter


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
    # github is the preferred (primary) provider; google is the only secondary —
    # so exactly one secondary button should appear.
    assert response.text.count('login-option-secondary') == 1


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
def test_adapter_post_login_sets_session_fields():
    """post_login() sets force-login timestamp and long-session flag."""
    user = User.objects.create_user('sso@example.com', 'password')
    request = RequestFactory().post('/accounts/login/', data={})
    request.user = user
    request.session = {}
    request.META['SERVER_NAME'] = 'localhost'
    request.META['SERVER_PORT'] = '80'
    request.host = 'localhost'
    setattr(request, '_messages', FallbackStorage(request))

    adapter = CustomAccountAdapter()
    response = adapter.post_login(
        request,
        user,
        email_verification=None,
        signal_kwargs=None,
        email=None,
        signup=False,
        redirect_url=None,
    )

    assert response.status_code == 302
    assert isinstance(request.session[KEY_LAST_FORCE_LOGIN], int)
    assert abs(import_time.time() - request.session[KEY_LAST_FORCE_LOGIN]) < 5
    assert request.session[KEY_LONG_SESSION] is False


@pytest.mark.django_db
def test_adapter_post_login_long_session_from_post():
    """post_login() sets KEY_LONG_SESSION=True when keep_logged_in is in POST data."""
    user = User.objects.create_user('long@example.com', 'password')
    request = RequestFactory().post('/accounts/login/', data={'keep_logged_in': '1'})
    request.user = user
    request.session = {}
    request.META['SERVER_NAME'] = 'localhost'
    request.META['SERVER_PORT'] = '80'
    request.host = 'localhost'
    setattr(request, '_messages', FallbackStorage(request))

    adapter = CustomAccountAdapter()
    adapter.post_login(
        request,
        user,
        email_verification=None,
        signal_kwargs=None,
        email=None,
        signup=False,
        redirect_url=None,
    )

    assert request.session[KEY_LONG_SESSION] is True


@pytest.mark.django_db
def test_adapter_post_login_reads_keep_logged_in_from_session():
    """Preferred-provider social login sets keep_logged_in via session flag."""
    user = User.objects.create_user('keep@example.com', 'password')
    request = RequestFactory().post('/accounts/login/', data={})
    request.user = user
    request.session = {KEY_SOCIAL_KEEP_LOGGED_IN: True}
    request.META['SERVER_NAME'] = 'localhost'
    request.META['SERVER_PORT'] = '80'
    request.host = 'localhost'
    setattr(request, '_messages', FallbackStorage(request))

    adapter = CustomAccountAdapter()
    adapter.post_login(
        request,
        user,
        email_verification=None,
        signal_kwargs=None,
        email=None,
        signup=False,
        redirect_url=None,
    )

    assert request.session[KEY_LONG_SESSION] is True
    # Session flag consumed
    assert KEY_SOCIAL_KEEP_LOGGED_IN not in request.session


@pytest.mark.django_db
def test_adapter_get_login_redirect_url_oauth2_handoff(monkeypatch):
    """When oauth2_params are in the session, redirect to the OAuth2 authorize endpoint."""
    user = User.objects.create_user('oauth2@example.com', 'password')
    request = RequestFactory().get('/')
    request.user = user
    request.session = {
        'oauth2_params': {
            'response_type': 'code',
            'client_id': 'test-client',
            'redirect_uri': 'https://example.com/callback',
            'scope': 'profile',
            'state': 'test-state',
        },
    }

    monkeypatch.setattr(
        'eventyay.eventyay_common.adapter.reverse',
        lambda name: '/oauth/authorize/',
    )

    adapter = CustomAccountAdapter()
    url = adapter.get_login_redirect_url(request)

    parsed = urlparse(url)
    assert '/oauth/authorize' in parsed.path
    params = parse_qs(parsed.query)
    assert params['client_id'] == ['test-client']
    assert params['state'] == ['test-state']
    # Consumed from session
    assert 'oauth2_params' not in request.session


@pytest.mark.django_db
def test_adapter_get_login_redirect_url_ignores_invalid_oauth2_params():
    """Invalid oauth2_params payload is discarded and fallback redirect is used."""
    user = User.objects.create_user('oauth2-invalid@example.com', 'password')
    request = RequestFactory().get('/')
    request.user = user
    request.session = {
        'oauth2_params': {
            'client_id': 'test-client',
            # Missing required redirect_uri and state keys.
            'scope': 'profile',
        },
        'socialauth_next_url': '/orga/my-event/',
    }

    adapter = CustomAccountAdapter()
    url = adapter.get_login_redirect_url(request)

    assert url == '/orga/my-event/'
    assert 'oauth2_params' not in request.session
    assert 'socialauth_next_url' not in request.session


@pytest.mark.django_db
def test_adapter_get_login_redirect_url_socialauth_next():
    """socialauth_next_url in session takes priority over default redirect."""
    user = User.objects.create_user('next@example.com', 'password')
    request = RequestFactory().get('/')
    request.user = user
    request.session = {'socialauth_next_url': '/orga/my-event/'}

    adapter = CustomAccountAdapter()
    url = adapter.get_login_redirect_url(request)

    assert url == '/orga/my-event/'
    assert 'socialauth_next_url' not in request.session


@pytest.mark.django_db
def test_social_adapter_syncs_wikimedia_username():
    """pre_social_login() syncs wikimedia_username from SocialAccount extra_data."""
    user = User.objects.create_user('wiki@example.com', 'password')
    assert user.wikimedia_username is None or user.wikimedia_username == ''

    # Enable the mediawiki provider in admin settings
    gs = GlobalSettingsObject()
    gs.settings.set('login_providers', {
        'mediawiki': {'state': True, 'client_id': 'x', 'secret': 'y'},
    })

    # Create a mock sociallogin with mediawiki extra_data
    class MockAccount:
        provider = 'mediawiki'
        uid = 'wiki-42'
        extra_data = {'username': 'WikiUser42', 'realname': 'Wiki User'}

    class MockSocialLogin:
        is_existing = True
        account = MockAccount()

        def __init__(self, user):
            self.user = user

    request = RequestFactory().get('/')
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))
    adapter = CustomSocialAccountAdapter(request)
    adapter.pre_social_login(request, MockSocialLogin(user))

    user.refresh_from_db()
    assert user.wikimedia_username == 'WikiUser42'


@pytest.mark.django_db
def test_social_adapter_rejects_disabled_provider():
    """pre_social_login() raises ImmediateHttpResponse for a disabled provider."""
    from allauth.core.exceptions import ImmediateHttpResponse

    user = User.objects.create_user('disabled@example.com', 'password')

    # Disable the mediawiki provider (state=False)
    gs = GlobalSettingsObject()
    gs.settings.set('login_providers', {
        'mediawiki': {'state': False, 'client_id': 'x', 'secret': 'y'},
    })

    class MockAccount:
        provider = 'mediawiki'
        extra_data = {}

    class MockSocialLogin:
        is_existing = True
        account = MockAccount()

        def __init__(self, user):
            self.user = user

    request = RequestFactory().get('/')
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))
    adapter = CustomSocialAccountAdapter(request)

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        adapter.pre_social_login(request, MockSocialLogin(user))

    assert exc_info.value.response.status_code == 302
    assert '/login' in exc_info.value.response['Location']


@pytest.mark.django_db
def test_social_adapter_rejects_unknown_provider():
    """pre_social_login() rejects a provider not in admin settings at all."""
    from allauth.core.exceptions import ImmediateHttpResponse

    user = User.objects.create_user('unknown@example.com', 'password')

    gs = GlobalSettingsObject()
    gs.settings.set('login_providers', {})  # No providers configured

    class MockAccount:
        provider = 'facebook'
        extra_data = {}

    class MockSocialLogin:
        is_existing = True
        account = MockAccount()

        def __init__(self, user):
            self.user = user

    request = RequestFactory().get('/')
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))
    adapter = CustomSocialAccountAdapter(request)

    with pytest.raises(ImmediateHttpResponse):
        adapter.pre_social_login(request, MockSocialLogin(user))


@pytest.mark.django_db
def test_social_adapter_rejects_enabled_but_unconfigured_provider():
    """pre_social_login() rejects a provider that is enabled but lacks credentials."""
    from allauth.core.exceptions import ImmediateHttpResponse

    user = User.objects.create_user('nocreds@example.com', 'password')

    gs = GlobalSettingsObject()
    gs.settings.set('login_providers', {
        'mediawiki': {'state': True, 'client_id': '', 'secret': ''},
    })

    class MockAccount:
        provider = 'mediawiki'
        extra_data = {}

    class MockSocialLogin:
        is_existing = True
        account = MockAccount()

        def __init__(self, user):
            self.user = user

    request = RequestFactory().get('/')
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))
    adapter = CustomSocialAccountAdapter(request)

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        adapter.pre_social_login(request, MockSocialLogin(user))

    assert exc_info.value.response.status_code == 302
