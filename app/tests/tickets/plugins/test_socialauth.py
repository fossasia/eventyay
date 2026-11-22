import re
import time as import_time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
import responses
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialAccount, SocialApp
from bs4 import BeautifulSoup
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.auth import SPAM_ACCOUNT_ERROR
from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject
from eventyay.common.consts import KEY_LAST_FORCE_LOGIN, KEY_LONG_SESSION, KEY_SOCIAL_KEEP_LOGGED_IN
from eventyay.eventyay_common.adapter import CustomAccountAdapter
from eventyay.eventyay_common.views.account.basic import get_social_account_provider_label
from eventyay.plugins.socialauth.adapter import CustomSocialAccountAdapter
from eventyay.plugins.socialauth.views import SocialLoginView


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


@pytest.mark.django_db
@pytest.mark.parametrize('provider', ['google', 'github', 'mediawiki'])
def test_social_and_account_adapter_rejects_spam_user(provider):
    """SSO pre_social_login and account pre_login reject spam users across all providers."""
    user = User.objects.create_user(f'spam_{provider}@example.com', 'password', is_spam=True)
    GlobalSettingsObject().settings.set('login_providers', {
        provider: {'state': True, 'client_id': 'id', 'secret': 'sec'},
    })

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


@pytest.mark.django_db
@pytest.mark.parametrize('issuer', [
    '', 'id.example', 'http://id.example', 'https:///realm', 'https://[broken',
    'https://invalid host.example', 'https://id.example/#', 'https://id.example:70000',
    'https://user:pass@id.example', 'https://id.example/realm?foo=bar',
])
def test_invalid_oidc_issuer_rolls_back_credentials(rf, issuer):
    view = SocialLoginView()
    view.post(rf.post('/', {'openid_connect_login': 'enabled'}))
    request = rf.post('/', {
        'save_credentials': 'credentials', 'previous_provider_id': '', 'openid_connect_issuer': issuer,
        'openid_connect_client_id': 'client', 'openid_connect_secret': 'secret',
        'github_client_id': 'client', 'github_secret': 'secret',
    })
    request.session = {}
    request._messages = FallbackStorage(request)
    view.post(request)
    assert any('issuer URL' in str(msg) for msg in request._messages)
    assert not SocialApp.objects.filter(provider__in=['github', 'openid_connect']).exists()
    assert not SocialLoginView().gs.settings.get('login_providers', as_type=dict)['github']['client_id']


@pytest.mark.django_db
def test_oidc_credential_rotation_and_stale_forms(rf):
    view = SocialLoginView()
    providers = {'openid_connect': {'state': True}}

    def save(issuer, marker, secret='secret'):
        view.update_credentials(rf.post('/', {
            'openid_connect_issuer': issuer, 'previous_provider_id': marker,
            'openid_connect_client_id': 'client', 'openid_connect_secret': secret,
        }), 'openid_connect', providers)

    first, second = 'https://first.example', 'https://second.example'
    save(first, '')
    alice = User.objects.create_user('alice@example.org', 'test')
    link = SocialAccount.objects.create(user=alice, provider='openid_connect', uid='alice')
    save(first, 'openid_connect', secret='rotated')
    assert SocialApp.objects.get(provider_id='openid_connect').secret == 'rotated'
    assert SocialAccount.objects.filter(pk=link.pk).exists()
    with pytest.raises(ValidationError, match='Reload'):
        save(second, '')
    save(second, 'openid_connect')
    save(first, providers['openid_connect']['provider_id'])
    with pytest.raises(ValidationError, match='Reload'):
        save(second, 'openid_connect')
    assert SocialApp.objects.get(provider='openid_connect').settings['server_url'] == first


@pytest.mark.django_db
@responses.activate
def test_admin_switch_and_return_through_oidc_callback(client, settings):
    settings.COMPRESS_ENABLED = False
    admin = User.objects.create_user('admin@example.org', 'test', is_staff=True)
    alice = User.objects.create_user('alice@example.org', 'test')
    EmailAddress.objects.create(user=alice, email=alice.email, primary=True, verified=True)
    github = SocialAccount.objects.create(user=alice, provider='github', uid='alice')
    url = reverse('plugins:socialauth:admin.global.social.auth.settings')
    for realm in ['first', 'second']:
        issuer = f'https://id.example/realms/{realm}'
        client.force_login(admin)
        admin.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
        if realm == 'first':
            client.post(url, {'openid_connect_login': 'enabled'})
        form = BeautifulSoup(client.get(url).content, 'html.parser')
        marker = form.select_one('[name=previous_provider_id]')['value']
        saved = client.post(url, {
            'save_credentials': 'credentials', 'previous_provider_id': marker,
            'openid_connect_display_name': 'APC Login' if realm == 'second' else '',
            'openid_connect_issuer': issuer, 'openid_connect_client_id': 'client', 'openid_connect_secret': 'secret',
        }, follow=True)
        callback = BeautifulSoup(saved.content, 'html.parser').select_one('#oidc-issuer').parent.code.text
        client.logout()
        responses.get(issuer + '/.well-known/openid-configuration', json={
            'issuer': issuer, 'authorization_endpoint': issuer + '/authorize',
            'token_endpoint': issuer + '/token', 'userinfo_endpoint': issuer + '/userinfo',
        })
        responses.post(issuer + '/token', json={'access_token': 'test-token', 'token_type': 'Bearer'})
        responses.get(issuer + '/userinfo', json={'email': alice.email, 'email_verified': True, 'sub': realm})
        if realm == 'second':
            assert client.get(reverse('openid_connect_callback', args=['openid_connect'])).status_code == 404
            assert 'Login with APC Login' in client.get(reverse('auth.login')).text
            request = RequestFactory().get('/')
            provider = get_adapter().get_provider(request, SocialApp.objects.get(provider='openid_connect').provider_id)
            login = provider.sociallogin_from_response(request, {
                'userinfo': {'sub': 'first', 'email': alice.email, 'email_verified': False},
            })
            login.lookup()
            assert not login.is_existing
        start = client.get(reverse('plugins:socialauth:social.oauth.login', args=['openid_connect']))
        authorization = client.get(start.url)
        params = parse_qs(urlparse(authorization.url).query)
        assert params['redirect_uri'] == [callback]
        client.get(urlparse(callback).path, {'code': 'test-code', 'state': params['state'][0]})
        assert int(client.session['_auth_user_id']) == alice.pk
        links = SocialAccount.objects.filter(user=alice).exclude(pk=github.pk)
        assert list(links.values_list('uid', flat=True)) == [realm]

        assert get_social_account_provider_label(alice) == ('APC Login' if realm == 'second' else 'OpenID Connect')

    assert SocialAccount.objects.filter(pk=github.pk).exists()
    client.force_login(admin)
    session = client.session
    session['eventyay_auth_login_time'] = import_time.time()
    session.save()
    admin.staffsession_set.create(date_start=now(), session_key=session.session_key)
    detail = reverse('eventyay_admin:admin.users.edit', kwargs={'id': alice.pk})
    for status in ('Active', 'Inactive provider'):
        page = BeautifulSoup(client.get(detail).content, 'html.parser')
        row = page.find('td', string='APC Login').parent
        assert row.select_one('.label').get_text(strip=True) == status
        if status == 'Active':
            client.post(url, {'openid_connect_login': 'disabled'})
    assert not SocialApp.objects.filter(provider='openid_connect').exists()
    client.post(url, {'openid_connect_login': 'enabled'})
    assert SocialApp.objects.get(provider='openid_connect').settings['server_url'] == issuer


@pytest.mark.django_db
def test_malformed_oidc_settings_leave_login_and_admin_available(client, preferred_login_providers):
    gs = GlobalSettingsObject()
    providers = gs.settings.get('login_providers', as_type=dict)
    gs.settings.set('login_providers', {**providers, 'openid_connect': 'disabled'})
    assert 'Login with Github' in client.get(reverse('auth.login')).text
    admin = User.objects.create_user('admin@example.org', 'test', is_staff=True)
    client.force_login(admin)
    admin.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
    page = client.get(reverse('plugins:socialauth:admin.global.social.auth.settings'))
    assert page.status_code == 200
    repaired = page.context['login_providers']
    assert not repaired['openid_connect']['state']
    assert repaired['github'] == providers['github']


@pytest.mark.django_db
def test_pending_oidc_signup_uses_current_account_provider(client, rf, settings):
    settings.EVENTYAY_REGISTRATION = True
    app = SocialApp.objects.create(provider='openid_connect', provider_id='openid_connect', client_id='client')
    signup = reverse('socialaccount_signup')

    def start_signup(provider_id):
        request = rf.get('/')
        provider = get_adapter().get_provider(request, provider_id)
        login = provider.sociallogin_from_response(request, {'userinfo': {'sub': 'new-user'}})
        session = client.session
        session['socialaccount_sociallogin'] = login.serialize()
        session.save()

    start_signup(app.provider_id)
    app.provider_id = 'oidc-second'
    app.save()
    assert client.post(signup, {'email': 'new@example.org'}).status_code == 302
    assert not SocialAccount.objects.filter(uid='new-user').exists()
    start_signup(app.provider_id)
    response = client.get(signup)
    assert response.status_code == 200
    assert response.context_data['form'].sociallogin.account.provider == app.provider_id
    client.post(signup, {'email': 'new@example.org'})
    assert SocialAccount.objects.get(uid='new-user').provider == app.provider_id


@pytest.mark.django_db
@pytest.mark.parametrize('preferred', [True, False])
def test_checkout_modal_uses_oidc_label(rf, preferred):
    GlobalSettingsObject().settings.set('login_providers', {'openid_connect': {
        'state': True, 'client_id': 'client', 'secret': 'secret',
        'display_name': 'Company login', 'is_preferred': preferred,
    }})
    html = render_to_string('pretixpresale/fragment_modals.html', request=rf.get('/'))
    assert 'Login with Company login' in html


@pytest.mark.django_db
def test_oidc_normalization_locks_before_updating():
    GlobalSettingsObject().settings.set('login_providers', {'openid_connect': {'display_name': 'Latest'}})
    with CaptureQueriesContext(connection) as queries:
        view = SocialLoginView()
    statements = [query['sql'] for query in queries]
    lock = next(i for i, sql in enumerate(statements) if 'FOR UPDATE' in sql)
    write = next(i for i, sql in enumerate(statements) if sql.startswith('UPDATE'))
    assert lock < write
    assert view.gs.settings.get('login_providers', as_type=dict)['openid_connect']['display_name'] == 'Latest'
