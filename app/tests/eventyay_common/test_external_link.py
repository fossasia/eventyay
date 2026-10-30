import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
import requests
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from bs4 import BeautifulSoup
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django_otp.plugins.otp_static.models import StaticDevice
from django_scopes import scope

from eventyay.api.models import OAuthApplication
from eventyay.base.middleware import SecurityMiddleware
from eventyay.base.models import SeatingPlan
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.views.redirect import safelink
from eventyay.common.redirects import safe_redirect_url
from eventyay.common.views import redirect_view
from eventyay.multidomain.models import KnownDomain
from eventyay.multidomain.urlreverse import eventreverse


EXTERNAL_LINK = '/common/external-link/'
DESTINATION = 'https://example.org/path?first=1&second=2#section'

pytestmark = pytest.mark.django_db


@pytest.fixture
def oauth_provider():
    GlobalSettingsObject().settings.set(
        'login_providers',
        {'google': {'state': True, 'client_id': 'test-client', 'secret': 'test-secret'}},
    )
    provider = Mock()
    provider.get_login_url.return_value = '/accounts/google/login/'
    with patch('eventyay.plugins.socialauth.views.get_adapter') as adapter:
        adapter.return_value.get_provider.return_value = provider
        yield provider


@pytest.mark.parametrize('client_fixture', ['client', 'authenticated_client'])
@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
def test_external_link_requires_confirmation(request, client_fixture, parameter):
    client = request.getfixturevalue(client_fixture)
    response = client.get(EXTERNAL_LINK, {parameter: DESTINATION, 'confirmed': '1'})

    assert response.status_code == 200
    assert 'Location' not in response
    page = BeautifulSoup(response.content, 'html.parser')
    assert 'You are leaving Eventyay' in page.get_text()
    assert DESTINATION in page.get_text()
    assert page.select_one('[data-external-link-continue]')['href'] == DESTINATION
    assert page.select_one('[data-external-link-continue]')['rel'] == ['noreferrer', 'noopener']
    assert page.select_one('[data-external-link-cancel]')['href'] == reverse('presale:index')
    assert not page.select('meta[http-equiv="refresh"]')
    assert response['Referrer-Policy'] == 'no-referrer'
    assert 'no-store' in response['Cache-Control']


@pytest.mark.parametrize(
    'destination',
    [
        '',
        'javascript:alert(1)',
        'data:text/html,<script>alert(1)</script>',
        'ftp://example.org/file',
        'https:///example.org',
        '///example.org',
        r'https://example.org\@evil.org/',
        'https://trusted.org@evil.org/',
        'https://example.org:invalid/',
        'https://[broken/',
        'https://example.org/\r\nLocation: https://evil.org',
        '\x00https://example.org',
    ],
)
def test_external_link_rejects_unsafe_destinations(client, destination):
    response = client.get(EXTERNAL_LINK, {'next': destination})
    assert response.status_code == 400
    assert 'Location' not in response


@pytest.mark.parametrize('destination', ['/common/organizers/', 'http://testserver/common/organizers/'])
def test_internal_destination_skips_warning(client, destination):
    response = client.get(EXTERNAL_LINK, {'next': destination})
    assert response.status_code == 302
    assert response.url == destination


def test_protocol_relative_destination_is_displayed_with_explicit_scheme(client):
    response = client.get(EXTERNAL_LINK, {'next': '//example.org/path'})
    assert response.status_code == 200
    assert response.context['destination'] == 'http://example.org/path'


def test_destination_is_escaped(client):
    destination = 'https://example.org/?text=<script>alert("x")</script>'
    response = client.get(EXTERNAL_LINK, {'next': destination})
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    assert page.select_one('[data-external-link-continue]')['href'] == destination
    assert '<script>alert("x")</script>' not in response.content.decode()


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
def test_authenticated_login_shows_warning(authenticated_client, parameter):
    response = authenticated_client.get(reverse('auth.login'), {parameter: DESTINATION}, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == EXTERNAL_LINK
    assert response.context['destination'] == DESTINATION


def test_successful_login_preserves_external_next(client, user):
    response = client.post(
        reverse('auth.login') + '?' + urlencode({'next': DESTINATION}),
        {'email': user.email, 'password': 'testpass123'},
        follow=True,
    )
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == EXTERNAL_LINK
    assert response.context['destination'] == DESTINATION


def test_two_factor_login_preserves_warning_until_authentication_finishes(client, user):
    user.require_2fa = True
    user.save()
    device = StaticDevice.objects.create(user=user)
    device.token_set.create(token='123456')
    response = client.post(
        reverse('auth.login') + '?' + urlencode({'next': DESTINATION}),
        {'email': user.email, 'password': 'testpass123'},
    )
    two_factor = urlsplit(response.url)
    assert two_factor.path == reverse('auth.login.2fa')
    warning = urlsplit(parse_qs(two_factor.query)['next'][0])
    assert warning.path == EXTERNAL_LINK
    assert parse_qs(warning.query) == {'next': [DESTINATION], 'return_url': [reverse('eventyay_common:dashboard')]}
    assert '_auth_user_id' not in client.session

    response = client.post(response.url, {'token': '123456'}, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == EXTERNAL_LINK
    assert response.context['destination'] == DESTINATION
    assert int(client.session['_auth_user_id']) == user.pk


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
def test_social_login_destination_requires_confirmation(client, oauth_provider, parameter):
    response = client.get(
        reverse('plugins:socialauth:social.oauth.login', args=['google']),
        {parameter: DESTINATION},
    )
    assert response.status_code == 302
    target = oauth_provider.get_login_url.call_args.kwargs['next']
    location = urlsplit(target)
    assert location.path == EXTERNAL_LINK
    assert parse_qs(location.query) == {'next': [DESTINATION], 'return_url': [reverse('eventyay_common:dashboard')]}
    assert 'socialauth_next_url' not in client.session
    response = client.get(target)
    assert response.status_code == 200
    assert response.context['destination'] == DESTINATION


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
@pytest.mark.parametrize('preferred', [False, True])
def test_login_page_preserves_destination_in_social_link(client, oauth_provider, parameter, preferred):
    gs = GlobalSettingsObject()
    providers = gs.settings.get('login_providers', as_type=dict)
    providers['google']['is_preferred'] = preferred
    gs.settings.set('login_providers', providers)
    response = client.get(reverse('auth.login'), {parameter: DESTINATION})
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    entry_url = reverse('plugins:socialauth:social.oauth.login', args=['google'])
    link = next(link for link in page.select('a[href]') if urlsplit(link['href']).path == entry_url)
    target = parse_qs(urlsplit(link['href']).query)['next'][0]
    assert target == safe_redirect_url(response.wsgi_request, DESTINATION)


@pytest.mark.parametrize(
    'destination',
    ['javascript:alert(1)', 'https://[broken/', 'https://trusted.org@evil.org/', r'https://example.org\@evil.org/'],
)
def test_social_login_rejects_unsafe_destination(client, oauth_provider, destination):
    response = client.get(
        reverse('plugins:socialauth:social.oauth.login', args=['google']),
        {'next': destination},
    )
    assert response.status_code == 302
    assert response.url == '/accounts/google/login/'
    assert oauth_provider.get_login_url.call_args.kwargs['next'] == reverse('eventyay_common:dashboard')
    assert 'socialauth_next_url' not in client.session


def test_social_login_preserves_internal_destination(client, oauth_provider):
    response = client.get(
        reverse('plugins:socialauth:social.oauth.login', args=['google']),
        {'next': '/common/organizers/'},
    )
    assert response.status_code == 302
    assert oauth_provider.get_login_url.call_args.kwargs['next'] == '/common/organizers/'


@pytest.mark.parametrize('signed', [False, True])
@pytest.mark.parametrize('public', [False, True])
def test_custom_domain_preserves_external_destination(client, event, settings, signed, public):
    settings.DEBUG = False
    settings.SITE_URL = 'https://platform.example'
    settings.SITE_NETLOC = 'platform.example'
    settings.ALLOWED_HOSTS = ['tickets.example', 'platform.example']
    event.custom_domain = 'https://tickets.example'
    event.is_public = public
    event.save()
    KnownDomain.objects.create(domainname='tickets.example', organizer=event.organizer, event=event)
    warning_params = {'next': DESTINATION}
    if signed:
        warning_params['return_url'] = reverse('presale:index')
    warning_url = EXTERNAL_LINK + '?' + urlencode(warning_params)
    response = client.get(
        safelink(DESTINATION) if signed else warning_url,
        HTTP_HOST='tickets.example',
        secure=True,
    )
    if signed:
        assert response.status_code == 302
        assert response.url == warning_url
        response = client.get(response.url, HTTP_HOST='tickets.example', secure=True)
    assert response.status_code == 302
    assert response.url == settings.SITE_URL + warning_url
    response = client.get(response.url, HTTP_HOST='platform.example', secure=True)
    assert response.status_code == 200
    assert response.context['destination'] == DESTINATION


def test_logout_back_requires_confirmation(authenticated_client):
    response = authenticated_client.get(reverse('eventyay_common:auth.logout'), {'back': DESTINATION}, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == EXTERNAL_LINK
    assert response.context['destination'] == DESTINATION
    assert '_auth_user_id' not in authenticated_client.session


def test_signed_external_link_shows_warning(client):
    response = client.get(safelink(DESTINATION), follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == EXTERNAL_LINK
    assert response.context['destination'] == DESTINATION


def test_signed_internal_link_keeps_destination(client):
    response = client.get(safelink('/common/organizers/'))
    assert response.status_code == 302
    assert response.url == '/common/organizers/'


def test_forged_signed_link_is_rejected(client):
    response = client.get(reverse('redirect'), {'url': DESTINATION})
    assert response.status_code == 400


@pytest.mark.parametrize('url_name', ['eventyay_common:auth.forgot', 'eventyay_common:auth.forgot.recover'])
def test_password_routes_preserve_destination_in_warning(authenticated_client, url_name):
    response = authenticated_client.get(reverse(url_name), {'next': DESTINATION})
    assert response.status_code == 302
    location = urlsplit(response.url)
    assert location.path == EXTERNAL_LINK
    assert parse_qs(location.query) == {'next': [DESTINATION], 'return_url': [reverse('eventyay_common:dashboard')]}


def test_confirmation_has_no_post_redirect_bypass(client):
    response = client.post(EXTERNAL_LINK, {'next': DESTINATION, 'confirmed': '1'})
    assert response.status_code == 405


@pytest.mark.parametrize('path', ['/', '/terms/', '/login/', '/common/forgot/'])
def test_public_navigation_loads_external_link_protection(client, path):
    response = client.get(path)
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    script = page.select_one('script[data-external-link-url]')
    assert script['data-external-link-url'] == EXTERNAL_LINK
    assert script['type'] == 'module'
    assert script['blocking'] == 'render'
    assert script.parent.name == 'head'


@pytest.mark.parametrize('destination', ['/common/organizers/', 'https://testserver/common/organizers/'])
def test_secure_internal_redirects_stay_internal(client, destination):
    response = client.get(EXTERNAL_LINK, {'next': destination}, secure=True)
    assert response.status_code == 302
    assert response.url == destination
    assert safe_redirect_url(response.wsgi_request, destination) == destination


def test_secure_request_does_not_silently_downgrade_to_http(client):
    destination = 'http://testserver/common/organizers/'
    response = client.get(EXTERNAL_LINK, {'next': destination}, secure=True)
    assert response.status_code == 200
    assert response.context['destination'] == destination
    assert safe_redirect_url(response.wsgi_request, destination) == EXTERNAL_LINK + '?' + urlencode(
        {'next': destination, 'return_url': reverse('eventyay_common:dashboard')}
    )


@pytest.mark.parametrize('referer', [None, 'http://testserver/common/organizers/'])
@pytest.mark.parametrize('destination', [DESTINATION, 'javascript:alert(1)', '/common/organizers/'])
def test_exported_signed_redirect_uses_shared_validation(rf, referer, destination):
    request = rf.get(safelink(destination))
    if referer:
        request.META['HTTP_REFERER'] = referer
    response = redirect_view(request)
    assert response.status_code == 302
    assert response.url == safe_redirect_url(request, destination, return_url=reverse('presale:index'))
    assert response['X-Robots-Tag'] == 'noindex'


def test_exported_signed_redirect_rejects_forged_signature(rf):
    assert redirect_view(rf.get('/redirect/', {'url': DESTINATION})).status_code == 400


@pytest.mark.parametrize('policy', [None, 'no-referrer'])
def test_security_middleware_sets_default_and_preserves_stricter_policy(rf, policy):
    response = HttpResponse()
    if policy:
        response['Referrer-Policy'] = policy
    response = SecurityMiddleware(lambda request: response).process_response(rf.get('/'), response)
    assert response['Referrer-Policy'] == (policy or 'strict-origin-when-cross-origin')


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
@pytest.mark.parametrize('preferred', [False, True])
@pytest.mark.parametrize('destination', [DESTINATION, '/common/organizers/'])
def test_signup_links_preserve_safe_destination(client, oauth_provider, parameter, preferred, destination):
    gs = GlobalSettingsObject()
    providers = gs.settings.get('login_providers', as_type=dict)
    providers['google']['is_preferred'] = preferred
    gs.settings.set('login_providers', providers)
    response = client.get(reverse('auth.login'), {parameter: destination})
    page = BeautifulSoup(response.content, 'html.parser')
    links = [link for link in page.select('a[href]') if urlsplit(link['href']).path == reverse('account_signup')]
    assert len(links) == 1
    collapsed_form = render_to_string(
        'eventyay_common/auth/_login_form.html',
        {
            'form': response.context['form'],
            'backends': response.context['backends'],
            'backend': response.context['backend'],
            'can_register': True,
            'next_url': response.context['next_url'],
            'force_show': False,
        },
        request=response.wsgi_request,
    )
    collapsed_page = BeautifulSoup(collapsed_form, 'html.parser')
    register_link = next(
        link for link in collapsed_page.select('a[href]') if urlsplit(link['href']).path == reverse('account_signup')
    )
    links.append(register_link)
    for link in links:
        target = parse_qs(urlsplit(link['href']).query)['next'][0]
        assert target == safe_redirect_url(response.wsgi_request, destination)
        signup = client.get(link['href'])
        assert signup.status_code == 200
        signup_page = BeautifulSoup(signup.content, 'html.parser')
        assert signup_page.select_one('input[name=next]')['value'] == target


def test_abandoned_social_flow_does_not_override_native_login(client, user, oauth_provider):
    client.get(reverse('plugins:socialauth:social.oauth.login', args=['google']), {'next': DESTINATION})
    session = client.session
    # Older sessions may still contain the previous, shared redirect state.
    session['socialauth_next_url'] = EXTERNAL_LINK + '?' + urlencode({'next': DESTINATION})
    session['oauth2_params'] = {
        'client_id': 'old-client',
        'redirect_uri': 'https://old.example/callback',
        'state': 'old',
    }
    session.save()
    response = client.post(
        reverse('auth.login') + '?' + urlencode({'next': '/common/organizers/'}),
        {'email': user.email, 'password': 'testpass123'},
    )
    assert response.status_code == 302
    assert response.url == '/common/organizers/'


@pytest.fixture
def callback_provider(user, monkeypatch):
    GlobalSettingsObject().settings.set(
        'login_providers',
        {'google': {'state': True, 'client_id': 'test-client', 'secret': 'test-secret'}},
    )
    SocialApp.objects.create(provider='google', client_id='test-client', secret='test-secret')
    SocialAccount.objects.create(user=user, provider='google', uid='google-user')
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    calls = []

    def provider_response(session, method, url, **kwargs):
        calls.append((method, url))
        if url == GoogleOAuth2Adapter.access_token_url:
            payload = {'access_token': 'test-access-token', 'token_type': 'Bearer', 'expires_in': 3600}
        elif url == GoogleOAuth2Adapter.identity_url:
            payload = {'id': 'google-user', 'email': user.email, 'verified_email': True}
        else:
            pytest.fail(f'Unexpected provider HTTP request: {method} {url}')
        response = requests.Response()
        response.status_code = 200
        response.headers['Content-Type'] = 'application/json'
        response._content = json.dumps(payload).encode()
        return response

    monkeypatch.setattr(requests.Session, 'request', provider_response)
    return calls


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
def test_social_login_callbacks_keep_destinations_when_completed_out_of_order(
    client, user, callback_provider, parameter
):
    application = OAuthApplication.objects.create(
        name='Talk',
        user=user,
        client_type='confidential',
        authorization_grant_type='authorization-code',
        redirect_uris='https://talk.example/callback',
    )
    authorize = (
        reverse('api-v1:authorize')
        + '?'
        + urlencode(
            {
                'client_id': application.client_id,
                'redirect_uri': 'https://talk.example/callback',
                'response_type': 'code',
                'scope': 'profile',
                'state': 'talk-state',
            }
        )
    )
    targets = [DESTINATION, authorize]
    states = []
    for target in targets:
        entry = client.get(reverse('plugins:socialauth:social.oauth.login', args=['google']), {parameter: target})
        provider = client.get(entry.url)
        assert provider.status_code == 302
        assert urlsplit(provider.url).hostname == 'accounts.google.com'
        states.append(parse_qs(urlsplit(provider.url).query)['state'][0])
    assert states[0] != states[1]
    for target, state in reversed(list(zip(targets, states))):
        response = client.get(reverse('google_callback'), {'state': state, 'code': 'test-authorization-code'})
        assert response.status_code == 302
        expected = (
            EXTERNAL_LINK + '?' + urlencode({'next': target, 'return_url': reverse('eventyay_common:dashboard')})
            if target == DESTINATION
            else target
        )
        assert response.url == expected
        assert int(client.session['_auth_user_id']) == user.pk
        if target == DESTINATION:
            confirmation = client.get(response.url)
            assert confirmation.status_code == 200
            assert confirmation.context['destination'] == DESTINATION
        else:
            consent = client.get(response.url)
            assert consent.status_code == 200
            assert 'Talk' in consent.text
    assert len(callback_provider) == 4


def test_social_login_without_next_does_not_reuse_previous_destination(client, oauth_provider):
    entry = reverse('plugins:socialauth:social.oauth.login', args=['google'])
    client.get(entry, {'next': DESTINATION})
    client.get(entry)
    assert oauth_provider.get_login_url.call_args.kwargs == {}


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
def test_signup_returns_to_confirmation_after_registration(client, settings, parameter):
    settings.ACCOUNT_EMAIL_VERIFICATION = 'none'
    login = client.get(reverse('auth.login'), {parameter: DESTINATION})
    page = BeautifulSoup(login.content, 'html.parser')
    signup_link = next(
        link['href'] for link in page.select('a[href]') if urlsplit(link['href']).path == reverse('account_signup')
    )
    target = parse_qs(urlsplit(signup_link).query)['next'][0]
    response = client.post(
        reverse('account_signup'),
        {
            'email': 'signup@example.org',
            'password1': 'TestPassword-6636!',
            'password2': 'TestPassword-6636!',
            'next': target,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == EXTERNAL_LINK
    assert response.context['destination'] == DESTINATION
    assert '_auth_user_id' in client.session


@pytest.mark.parametrize('has_subevents', [False, True])
def test_standalone_seating_plan_loads_link_protection(client, event, has_subevents):
    plan = SeatingPlan.objects.create(organizer=event.organizer, name='Seating', layout='{}')
    event.has_subevents = has_subevents
    event.tickets_published = True
    if not has_subevents:
        event.seating_plan = plan
    event.save()
    kwargs = {}
    if has_subevents:
        with scope(event=event, organizer=event.organizer):
            subevent = event.subevents.create(
                name='Seated date', date_from=event.date_from, seating_plan=plan, active=True
            )
        kwargs['subevent'] = subevent.pk
    plugin_html = f'<a id="plugin-link" href="{DESTINATION}">External seating link</a>'
    with patch('eventyay.presale.signals.render_seating_plan.send', return_value=[(None, plugin_html)]):
        response = client.get(eventreverse(event, 'presale:event.seatingplan', kwargs=kwargs))
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    assert page.select_one('#plugin-link')['href'] == DESTINATION
    script = page.select_one('head script[data-external-link-url]')
    assert script is not None
    assert script['data-external-link-url'] == EXTERNAL_LINK
    assert script['type'] == 'module'
    assert script['blocking'] == 'render'


def test_standalone_signup_page_loads_link_protection(client):
    response = client.get(reverse('account_signup'))
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    script = page.select_one('head script[data-external-link-url]')
    assert script is not None
    assert script['data-external-link-url'] == EXTERNAL_LINK
    assert script['type'] == 'module'
    assert script['blocking'] == 'render'
