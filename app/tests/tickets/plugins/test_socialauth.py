import re
import time as import_time
from types import SimpleNamespace

import pytest
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse

from eventyay.base.auth import SPAM_ACCOUNT_ERROR
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
    response = client.get(reverse('auth.login'))

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
        reverse('auth.login'),
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
@pytest.mark.parametrize(
    'stale_state',
    [
        {'socialauth_next_url': '/orga/my-event/'},
        {
            'oauth2_params': {
                'client_id': 'test-client',
                'redirect_uri': 'https://example.com/callback',
                'state': 'test-state',
            }
        },
        {'oauth2_params': {'client_id': 'test-client'}, 'socialauth_next_url': '/orga/my-event/'},
    ],
)
def test_adapter_ignores_destinations_from_abandoned_social_flows(settings, stale_state):
    request = RequestFactory().get('/')
    request.session = stale_state
    request.user = User.objects.create_user('abandoned@example.org', 'password')
    settings.LOGIN_REDIRECT_URL = '/common/account/general'

    assert CustomAccountAdapter().get_login_redirect_url(request) == settings.LOGIN_REDIRECT_URL


@pytest.mark.django_db
def test_social_adapter_syncs_wikimedia_username():
    """pre_social_login() syncs wikimedia_username from SocialAccount extra_data."""
    user = User.objects.create_user('wiki@example.com', 'password')
    assert user.wikimedia_username is None or user.wikimedia_username == ''

    # Enable the mediawiki provider in admin settings
    gs = GlobalSettingsObject()
    gs.settings.set(
        'login_providers',
        {
            'mediawiki': {'state': True, 'client_id': 'x', 'secret': 'y'},
        },
    )

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
    gs.settings.set(
        'login_providers',
        {
            'mediawiki': {'state': False, 'client_id': 'x', 'secret': 'y'},
        },
    )

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
    gs.settings.set(
        'login_providers',
        {
            'mediawiki': {'state': True, 'client_id': '', 'secret': ''},
        },
    )

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


@pytest.mark.django_db
@pytest.mark.parametrize('provider', ['google', 'github', 'mediawiki'])
def test_social_and_account_adapter_rejects_spam_user(provider):
    """SSO pre_social_login and account pre_login reject spam users across all providers."""
    user = User.objects.create_user(f'spam_{provider}@example.com', 'password', is_spam=True)
    GlobalSettingsObject().settings.set(
        'login_providers',
        {
            provider: {'state': True, 'client_id': 'id', 'secret': 'sec'},
        },
    )

    request = RequestFactory().get('/')
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))

    sociallogin = SimpleNamespace(
        is_existing=True,
        user=user,
        account=SimpleNamespace(provider=provider, extra_data={}),
    )
    with pytest.raises(ImmediateHttpResponse) as exc_info:
        CustomSocialAccountAdapter(request).pre_social_login(request, sociallogin)

    assert exc_info.value.response.status_code == 302
    assert exc_info.value.response['Location'] == reverse('auth.login')

    with pytest.raises(ImmediateHttpResponse) as exc_info:
        CustomAccountAdapter().pre_login(
            request, user, email_verification=None, signal_kwargs=None, email=None, signup=False, redirect_url=None
        )
    assert exc_info.value.response['Location'] == reverse('auth.login')
    messages = [str(m.message) for m in getattr(request, '_messages')]
    assert str(SPAM_ACCOUNT_ERROR) in messages


def test_login_providers_schema_supports_openid_connect():
    from eventyay.plugins.socialauth.schemas.login_providers import LoginProviders

    # 1. Existing providers without openid_connect should validate and backfill default openid_connect
    data = {
        'mediawiki': {'state': False, 'client_id': '', 'secret': '', 'is_preferred': False},
        'github': {'state': True, 'client_id': 'gh_id', 'secret': 'gh_sec', 'is_preferred': False},
        'google': {'state': False, 'client_id': '', 'secret': '', 'is_preferred': False},
    }
    validated = LoginProviders.model_validate(data)
    dumped = validated.model_dump()
    assert 'openid_connect' in dumped
    assert dumped['openid_connect']['state'] is False
    assert dumped['openid_connect']['server_url'] == ''

    # 2. Configured openid_connect should validate all fields
    data['openid_connect'] = {
        'state': True,
        'client_id': 'keycloak_client',
        'secret': 'keycloak_secret',
        'server_url': 'https://auth.example.com/realms/master',
        'name': 'Corporate SSO',
        'is_preferred': True,
    }
    validated_oidc = LoginProviders.model_validate(data)
    dumped_oidc = validated_oidc.model_dump()
    assert dumped_oidc['openid_connect']['state'] is True
    assert dumped_oidc['openid_connect']['server_url'] == 'https://auth.example.com/realms/master'
    assert dumped_oidc['openid_connect']['name'] == 'Corporate SSO'
    assert dumped_oidc['openid_connect']['is_preferred'] is True


def test_order_login_providers_validates_openid_connect_server_url():
    from eventyay.eventyay_common.services.auth_providers import get_preferred_provider, order_login_providers

    providers = {
        'openid_connect': {
            'state': True,
            'client_id': 'client_id',
            'secret': 'secret',
            'server_url': '',  # missing server_url!
            'is_preferred': True,
        },
        'github': {
            'state': True,
            'client_id': 'gh_client',
            'secret': 'gh_secret',
            'is_preferred': False,
        },
    }
    # openid_connect without server_url must not be considered valid
    ordered = order_login_providers(providers)
    assert 'openid_connect' not in ordered
    assert 'github' in ordered

    # openid_connect with server_url is valid and ordered first when preferred
    providers['openid_connect']['server_url'] = 'https://auth.example.com/realms/master'
    ordered2 = order_login_providers(providers)
    assert list(ordered2.keys())[0] == 'openid_connect'
    assert get_preferred_provider(providers) == 'openid_connect'


def test_get_login_context_merges_env_oidc(settings):
    from unittest import mock

    from eventyay.eventyay_common.templatetags.auth_login_tags import get_login_context

    settings.OIDC_ENABLED = True
    settings.OIDC_SERVER_URL = 'https://keycloak.example.com/realms/myrealm'
    settings.OIDC_CLIENT_ID = 'eventyay-web'
    settings.OIDC_CLIENT_SECRET = 'supersecret'
    settings.OIDC_PROVIDER_NAME = 'Keycloak SSO'
    settings.OIDC_PREFERRED = True

    context = {'request': None}
    with mock.patch('eventyay.eventyay_common.templatetags.auth_login_tags.GlobalSettingsObject') as mock_gs:
        mock_gs.return_value.settings.get.return_value = {}
        login_ctx = get_login_context(context)

    assert login_ctx['has_oauth_providers'] is True
    assert login_ctx['preferred_provider'] == 'openid_connect'
    assert login_ctx['preferred_provider_name'] == 'Keycloak SSO'
    providers_dict = dict(login_ctx['enabled_providers'])
    assert 'openid_connect' in providers_dict
    assert providers_dict['openid_connect']['server_url'] == 'https://keycloak.example.com/realms/myrealm'


def test_oauth_login_view_rejects_missing_openid_connect_server_url():
    from unittest import mock

    from eventyay.plugins.socialauth.views import OAuthLoginView

    rf = RequestFactory()
    request = rf.get('/control/admin/global/socialauth/login/openid_connect')
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))

    with mock.patch('eventyay.plugins.socialauth.views.GlobalSettingsObject') as mock_gs:
        mock_gs.return_value.settings.get.return_value = {
            'openid_connect': {
                'state': True,
                'client_id': 'id',
                'secret': 'sec',
                'server_url': '',  # empty server_url
            }
        }
        view = OAuthLoginView.as_view()
        response = view(request, provider='openid_connect')

    assert response.status_code == 302
    assert response['Location'] == reverse('auth.login')
    messages = [str(m.message) for m in getattr(request, '_messages')]
    assert 'This login method is not available.' in messages


def test_social_adapter_allows_env_configured_oidc(settings):
    from unittest import mock

    from eventyay.plugins.socialauth.adapter import require_provider_enabled

    settings.OIDC_ENABLED = True
    settings.OIDC_SERVER_URL = 'https://auth.example.com/realms/master'
    settings.OIDC_CLIENT_ID = 'client_123'
    settings.OIDC_CLIENT_SECRET = 'secret_123'

    request = RequestFactory().get('/')
    request.session = {}
    setattr(request, '_messages', FallbackStorage(request))

    with mock.patch('eventyay.plugins.socialauth.adapter.GlobalSettingsObject') as mock_gs:
        mock_gs.return_value.settings.get.return_value = {}
        # Should not raise ImmediateHttpResponse
        require_provider_enabled(request, 'openid_connect')


def test_social_login_view_update_credentials_openid_connect():
    from unittest import mock

    from eventyay.plugins.socialauth.views import SocialLoginView

    rf = RequestFactory()
    post_data = {
        'openid_connect_client_id': 'oidc-client-1',
        'openid_connect_secret': 'oidc-secret-1',
        'openid_connect_server_url': 'https://auth.example.com/realms/eventyay',
        'openid_connect_name': 'My Company SSO',
    }
    request = rf.post('/control/admin/global/socialauth/', data=post_data)

    login_providers = {'openid_connect': {}}

    with mock.patch('allauth.socialaccount.models.SocialApp.objects.update_or_create') as mock_update_or_create:
        view = SocialLoginView.__new__(SocialLoginView)
        view.gs = mock.MagicMock()
        view.update_credentials(request, 'openid_connect', login_providers)

    mock_update_or_create.assert_called_once_with(
        provider='openid_connect',
        defaults={
            'client_id': 'oidc-client-1',
            'secret': 'oidc-secret-1',
            'provider_id': 'openid_connect',
            'name': 'My Company SSO',
            'settings': {'server_url': 'https://auth.example.com/realms/eventyay'},
        },
    )
    assert login_providers['openid_connect']['server_url'] == 'https://auth.example.com/realms/eventyay'
    assert login_providers['openid_connect']['name'] == 'My Company SSO'
