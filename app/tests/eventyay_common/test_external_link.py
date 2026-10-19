from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django_otp.plugins.otp_static.models import StaticDevice

from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.views.redirect import safelink
from eventyay.eventyay_common.adapter import CustomAccountAdapter
from eventyay.multidomain.models import KnownDomain


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
    assert page.select_one('[data-external-link-cancel]')['href'] == reverse('eventyay_common:dashboard')
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
    assert parse_qs(warning.query) == {'next': [DESTINATION]}
    assert '_auth_user_id' not in client.session

    response = client.post(response.url, {'token': '123456'}, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'] == EXTERNAL_LINK
    assert response.context['destination'] == DESTINATION
    assert int(client.session['_auth_user_id']) == user.pk


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
def test_social_login_destination_requires_confirmation(client, rf, oauth_provider, parameter):
    response = client.get(
        reverse('plugins:socialauth:social.oauth.login', args=['google']),
        {parameter: DESTINATION},
    )
    assert response.status_code == 302
    assert response.url == '/accounts/google/login/'
    request = rf.get('/accounts/login/')
    request.session = client.session
    target = CustomAccountAdapter().get_login_redirect_url(request)
    location = urlsplit(target)
    assert location.path == EXTERNAL_LINK
    assert parse_qs(location.query) == {'next': [DESTINATION]}
    assert 'socialauth_next_url' not in request.session
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
    assert parse_qs(urlsplit(link['href']).query) == {'next': [DESTINATION]}


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
    assert client.session['socialauth_next_url'] == reverse('eventyay_common:dashboard')


def test_social_login_preserves_internal_destination(client, rf, oauth_provider):
    response = client.get(
        reverse('plugins:socialauth:social.oauth.login', args=['google']),
        {'next': '/common/organizers/'},
    )
    assert response.status_code == 302
    request = rf.get('/accounts/login/')
    request.session = client.session
    assert CustomAccountAdapter().get_login_redirect_url(request) == '/common/organizers/'


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
    warning_url = EXTERNAL_LINK + '?' + urlencode({'next': DESTINATION})
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
    assert parse_qs(location.query) == {'next': [DESTINATION]}


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
