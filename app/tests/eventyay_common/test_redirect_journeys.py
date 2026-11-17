import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import pytest
from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.urls import reverse
from django_otp.plugins.otp_static.models import StaticDevice

from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.views.redirect import safelink as base_safelink
from eventyay.common.redirects import external_link_origin, safe_redirect_url
from eventyay.common.views.redirect import safelink as common_safelink
from eventyay.eventyay_common.views.auth import process_login
from eventyay.multidomain.models import KnownDomain
from eventyay.multidomain.urlreverse import eventreverse


pytestmark = pytest.mark.django_db
DESTINATION = 'https://external.example/event?lang=en&ticket=1#details'
INTERNAL = 'https://testserver/common/organizers/?tab=events#upcoming'
WARNING = '/common/external-link/'


@pytest.mark.parametrize('source', ['query', 'form'])
@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
@pytest.mark.parametrize('destination', ['/common/organizers/?tab=events#upcoming', INTERNAL])
def test_native_login_keeps_valid_internal_destination(client, user, parameter, destination, source):
    url = reverse('auth.login')
    data = {'email': user.email, 'password': 'testpass123'}
    if source == 'form':
        data[parameter] = destination
    else:
        url += '?' + urlencode({parameter: destination})
    response = client.post(url, data, secure=True)
    assert response.status_code == 302
    assert response.url == destination
    assert int(client.session['_auth_user_id']) == user.pk


@pytest.mark.parametrize('source', ['query', 'form'])
@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
@pytest.mark.parametrize('destination', [INTERNAL, DESTINATION])
def test_two_factor_keeps_destination_through_retry(client, user, settings, parameter, destination, source):
    settings.OTP_STATIC_THROTTLE_FACTOR = 0
    user.require_2fa = True
    user.save()
    device = StaticDevice.objects.create(user=user)
    device.token_set.create(token='123456')
    response = client.post(
        reverse('auth.login') + '?' + urlencode({parameter: destination}),
        {'email': user.email, 'password': 'testpass123'},
        secure=True,
    )
    target = safe_redirect_url(response.wsgi_request, destination)
    assert parse_qs(urlsplit(response.url).query).get('next') == [target]
    assert '_auth_user_id' not in client.session

    retry_url = reverse('auth.login.2fa') if source == 'form' else response.url
    retry_data = {'token': 'incorrect'}
    if source == 'form':
        retry_data[parameter] = destination
    response = client.post(retry_url, retry_data, secure=True)
    assert urlsplit(response.url).path == reverse('auth.login.2fa')
    assert parse_qs(urlsplit(response.url).query).get('next') == [target]
    assert '_auth_user_id' not in client.session

    success_url = reverse('auth.login.2fa') if source == 'form' else response.url
    success_data = {'token': '123456'}
    if source == 'form':
        success_data[parameter] = destination
    response = client.post(success_url, success_data, secure=True)
    assert response.url == target
    assert int(client.session['_auth_user_id']) == user.pk


@pytest.mark.parametrize('method', ['get', 'post'])
def test_expired_two_factor_keeps_destination_on_return_to_login(client, user, method):
    session = client.session
    session['eventyay_auth_2fa_user'] = user.pk
    session['eventyay_auth_2fa_time'] = str(int(time.time()) - 600)
    session.save()
    response = getattr(client, method)(reverse('auth.login.2fa'), {'next': DESTINATION}, secure=True)
    assert urlsplit(response.url).path == reverse('auth.login')
    assert parse_qs(urlsplit(response.url).query).get('next') == [safe_redirect_url(response.wsgi_request, DESTINATION)]


@pytest.mark.parametrize('client_fixture', ['client', 'authenticated_client'])
def test_public_cancel_returns_to_source_page(request, client_fixture):
    client = request.getfixturevalue(client_fixture)
    source = 'https://testserver/terms/?lang=en#privacy'
    response = client.get(WARNING, {'next': DESTINATION, 'return_url': source}, secure=True)
    page = BeautifulSoup(response.content, 'html.parser')
    assert response.status_code == 200
    assert page.select_one('[data-external-link-cancel]')['href'] == source
    assert page.select_one('[data-external-link-continue]')['href'] == DESTINATION
    assert 'Location' not in response


@pytest.mark.parametrize(
    'return_url',
    [
        'https://evil.example/phishing',
        '//evil.example/phishing',
        'javascript:alert(1)',
        'https://testserver@evil.example/',
        'https://[broken/',
        r'/\evil.example/',
        'http://testserver/terms/',
        '/common/external-link/?next=https://evil.example/',
        '/redirect/?url=forged',
        '/common/external-link?next=https://evil.example/',
        '/redirect?url=forged',
        'https://testserver/common/external-link?next=https://evil.example/',
        'https://testserver/redirect?url=forged',
    ],
)
def test_cancel_rejects_unsafe_return_without_another_warning(client, return_url):
    response = client.get(WARNING, {'next': DESTINATION, 'return_url': return_url}, secure=True)
    page = BeautifulSoup(response.content, 'html.parser')
    assert response.status_code == 200
    assert page.select_one('[data-external-link-cancel]')['href'] == reverse('presale:index')


@pytest.mark.parametrize('client_fixture', ['client', 'authenticated_client'])
def test_auth_warning_keeps_dashboard_cancel(request, client_fixture, rf):
    client = request.getfixturevalue(client_fixture)
    warning = safe_redirect_url(rf.get('/login/', secure=True), DESTINATION)
    response = client.get(warning, secure=True)
    page = BeautifulSoup(response.content, 'html.parser')
    assert page.select_one('[data-external-link-cancel]')['href'] == reverse('eventyay_common:dashboard')


def test_signed_public_link_keeps_source_page(client):
    source = client.get('/terms/?lang=en', secure=True)
    signed_link = render_to_string(
        'common/includes/core_footer.html',
        {'core_footer_links': [{'url': DESTINATION, 'label': 'External', 'target_blank': False}]},
        request=source.wsgi_request,
    )
    link = BeautifulSoup(signed_link, 'html.parser').select_one('a[href]')['href']
    response = client.get(link, follow=True, secure=True)
    page = BeautifulSoup(response.content, 'html.parser')
    assert response.status_code == 200
    assert response.context['destination'] == DESTINATION
    assert page.select_one('[data-external-link-cancel]')['href'] == 'https://testserver/terms/?lang=en'


@pytest.mark.parametrize('signed', [False, True])
def test_public_cancel_survives_custom_domain_handoff(client, event, settings, signed):
    settings.DEBUG = False
    settings.SITE_URL = 'https://platform.example'
    settings.SITE_NETLOC = 'platform.example'
    settings.ALLOWED_HOSTS = ['tickets.example', 'platform.example']
    event.custom_domain = 'https://tickets.example'
    event.tickets_published = True
    event.save()
    KnownDomain.objects.create(domainname='tickets.example', organizer=event.organizer, event=event)
    source = client.get(
        eventreverse(event, 'presale:event.index') + '?lang=en', HTTP_HOST='tickets.example', secure=True, follow=True
    )
    assert source.status_code == 200
    source_url = source.wsgi_request.build_absolute_uri()
    if signed:
        html = render_to_string(
            'common/includes/core_footer.html',
            {'core_footer_links': [{'url': DESTINATION, 'label': 'External', 'target_blank': False}]},
            request=source.wsgi_request,
        )
        url = BeautifulSoup(html, 'html.parser').select_one('a[href]')['href']
        response = client.get(url, HTTP_HOST='tickets.example', secure=True)
        url = response.url
    else:
        script = BeautifulSoup(source.content, 'html.parser').select_one('script[data-external-link-url]')
        url = (
            WARNING
            + '?'
            + urlencode(
                {
                    'next': DESTINATION,
                    'return_url': source_url + '#speakers',
                    'return_origin': script.get('data-external-link-origin', 'missing'),
                }
            )
        )
    response = client.get(url, HTTP_HOST='tickets.example', secure=True)
    assert response.status_code == 302
    assert response.url.startswith(settings.SITE_URL + WARNING)
    response = client.get(response.url, HTTP_HOST='platform.example', secure=True)
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    assert page.select_one('[data-external-link-cancel]')['href'] == source_url + ('' if signed else '#speakers')
    assert page.select_one('[data-external-link-continue]')['href'] == DESTINATION


@pytest.mark.parametrize('tamper', ['token', 'host', 'scheme', 'port'])
def test_return_origin_cannot_authorize_another_host_or_scheme(client, tamper):
    source = client.get('/terms/', secure=True)
    script = BeautifulSoup(source.content, 'html.parser').select_one('script[data-external-link-url]')
    token = script.get('data-external-link-origin', 'missing')
    return_url = 'https://other.example/terms/'
    if tamper == 'token':
        token += 'tampered'
    if tamper == 'scheme':
        return_url = 'http://testserver/terms/'
    if tamper == 'port':
        return_url = 'https://testserver:8443/terms/'
    response = client.get(WARNING, {'next': DESTINATION, 'return_url': return_url, 'return_origin': token}, secure=True)
    page = BeautifulSoup(response.content, 'html.parser')
    assert page.select_one('[data-external-link-cancel]')['href'] == reverse('presale:index')


@pytest.mark.parametrize('preferred', [False, True])
@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
@pytest.mark.parametrize('destination', [INTERNAL, DESTINATION])
def test_lost_password_link_keeps_effective_destination(client, preferred, parameter, destination):
    GlobalSettingsObject().settings.set(
        'login_providers',
        {
            'google': {'state': True, 'client_id': 'client', 'secret': 'secret', 'is_preferred': preferred},
        },
    )
    response = client.get(reverse('auth.login'), {parameter: destination}, secure=True)
    page = BeautifulSoup(response.content, 'html.parser')
    link = next(
        link for link in page.select('a[href]') if urlsplit(link['href']).path == reverse('eventyay_common:auth.forgot')
    )
    target = safe_redirect_url(response.wsgi_request, destination)
    assert parse_qs(urlsplit(link['href']).query).get('next') == [target]
    forgot = client.get(link['href'], secure=True)
    form = BeautifulSoup(forgot.content, 'html.parser').select_one('form')
    action = urljoin(forgot.wsgi_request.build_absolute_uri(), form.get('action', ''))
    assert parse_qs(urlsplit(action).query).get('next') == [target]


@pytest.mark.parametrize('source', ['query', 'form'])
@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
@pytest.mark.parametrize('destination', [INTERNAL, DESTINATION, 'javascript:alert(1)'])
def test_password_recovery_email_and_login_keep_safe_destination(
    client, user, settings, parameter, destination, source
):
    settings.HAS_REDIS = False
    forgot_url = reverse('eventyay_common:auth.forgot')
    data = {'email': user.email}
    if source == 'form':
        data[parameter] = destination
    else:
        forgot_url += '?' + urlencode({parameter: destination})
    with patch('eventyay.base.services.mail.mail') as deliver:
        response = client.post(forgot_url, data, secure=True)
    assert response.status_code == 302
    target = safe_redirect_url(response.wsgi_request, destination)
    deliver.assert_called_once()
    recovery_url = deliver.call_args.args[3]['url']
    assert parse_qs(urlsplit(recovery_url).query).get('next') == [target]
    assert parse_qs(urlsplit(response.url).query).get('next') == [target]

    recovery = client.get(recovery_url, secure=True)
    assert recovery.status_code == 200
    password = 'N3w-Passw0rd!X'
    data = {'password': password, 'password_repeat': password}
    if source == 'form':
        params = parse_qs(urlsplit(recovery_url).query)
        del params['next']
        recovery_url = reverse('eventyay_common:auth.forgot.recover') + '?' + urlencode(params, doseq=True)
        data[parameter] = target
    response = client.post(recovery_url, data, secure=True)
    assert response.status_code == 302
    assert urlsplit(response.url).path == reverse('auth.login')
    assert parse_qs(urlsplit(response.url).query).get('next') == [target]
    response = client.post(response.url, {'email': user.email, 'password': password}, secure=True)
    assert response.url == target
    user.refresh_from_db()
    assert user.check_password(password)
    if destination == DESTINATION:
        warning = client.get(response.url, secure=True)
        assert warning.status_code == 200
        assert 'Location' not in warning
        assert warning.context['destination'] == destination


@pytest.mark.parametrize('valid_user', [False, True])
def test_forgot_confirmation_keeps_destination_without_disclosing_account(client, user, settings, valid_user):
    settings.HAS_REDIS = False
    with patch('eventyay.base.services.mail.mail'):
        response = client.post(
            reverse('eventyay_common:auth.forgot') + '?' + urlencode({'next': DESTINATION}),
            {'email': user.email if valid_user else 'unknown@example.org'},
            secure=True,
        )
    assert response.status_code == 302
    assert urlsplit(response.url).path == reverse('eventyay_common:auth.forgot')
    assert parse_qs(urlsplit(response.url).query).get('next') == [safe_redirect_url(response.wsgi_request, DESTINATION)]
    confirmation = client.get(response.url, secure=True)
    assert 'If the address is registered' in confirmation.content.decode()


def test_invalid_recovery_keeps_destination_on_return_to_forgot(client, user):
    response = client.get(
        reverse('eventyay_common:auth.forgot.recover'),
        {
            'id': user.pk,
            'token': 'tampered',
            'next': DESTINATION,
        },
        secure=True,
    )
    assert urlsplit(response.url).path == reverse('eventyay_common:auth.forgot')
    assert parse_qs(urlsplit(response.url).query).get('next') == [safe_redirect_url(response.wsgi_request, DESTINATION)]


def test_admin_password_reset_does_not_inherit_page_destination(user, rf):
    request = rf.get('/control/users/', {'next': DESTINATION}, secure=True)
    with patch('eventyay.base.services.mail.mail') as deliver:
        user.send_password_reset(request, sync_send=True)
    params = parse_qs(urlsplit(deliver.call_args.args[3]['url']).query)
    assert set(params) == {'id', 'token'}
    assert default_token_generator.check_token(user, params['token'][0])
    assert deliver.call_args.kwargs['sync_send'] is True


def test_secure_warning_rejects_http_return_even_with_source_signature(client):
    source = client.get('/terms/')
    script = BeautifulSoup(source.content, 'html.parser').select_one('script[data-external-link-url]')
    response = client.get(
        WARNING,
        {
            'next': DESTINATION,
            'return_url': 'http://testserver/terms/',
            'return_origin': script['data-external-link-origin'],
        },
        secure=True,
    )
    page = BeautifulSoup(response.content, 'html.parser')
    assert page.select_one('[data-external-link-cancel]')['href'] == reverse('presale:index')


@pytest.mark.parametrize('destination', [INTERNAL, DESTINATION])
@pytest.mark.parametrize('two_factor', [False, True])
def test_explicit_login_destination_overrides_query_and_stale_social_state(client, user, rf, destination, two_factor):
    user.require_2fa = two_factor
    user.save(update_fields=['require_2fa'])
    request = rf.post(reverse('auth.login') + '?' + urlencode({'next': '/common/organizers/'}), secure=True)
    request.user = AnonymousUser()
    request.session = client.session
    request.session['socialauth_next_url'] = 'https://stale.example/'
    target = safe_redirect_url(request, destination)

    response = process_login(request, user, keep_logged_in=False, next_url=destination)

    assert response.status_code == 302
    if two_factor:
        assert urlsplit(response.url).path == reverse('auth.login.2fa')
        assert parse_qs(urlsplit(response.url).query)['next'] == [target]
        assert '_auth_user_id' not in request.session
    else:
        assert response.url == target
        assert int(request.session['_auth_user_id']) == user.pk


@pytest.mark.parametrize('link_builder', [base_safelink, common_safelink])
def test_signed_link_entry_points_keep_destination_and_cancel_context(client, link_builder):
    source = 'https://testserver/terms/?lang=en&name=A+B#privacy'
    destination = 'https://external.example/event?name=A+B&note=%2B%26%3D#details'
    url = link_builder(destination, return_url=source)

    response = client.get(url, secure=True, follow=True)

    assert response.status_code == 200
    assert response.request['PATH_INFO'] == WARNING
    assert 'Location' not in response
    page = BeautifulSoup(response.content, 'html.parser')
    assert page.select_one('[data-external-link-continue]')['href'] == destination
    assert page.select_one('[data-external-link-cancel]')['href'] == source


@pytest.mark.parametrize('parameter', ['next', 'redirect_url'])
def test_submitted_login_destination_takes_precedence_over_query(client, user, parameter):
    response = client.post(
        reverse('auth.login') + '?' + urlencode({'next': '/terms/'}),
        {'email': user.email, 'password': 'testpass123', parameter: DESTINATION},
        secure=True,
    )
    warning = client.get(response.url, secure=True)
    assert warning.status_code == 200
    assert warning.context['destination'] == DESTINATION


def test_backend_state_still_controls_login_destination(client, settings):
    settings.EVENTYAY_AUTH_BACKENDS = [
        'eventyay.base.auth.NativeAuthBackend',
        'tests.tickets.testdummy.auth.TestRequestAuthBackend',
    ]
    response = client.get(
        reverse('auth.login'),
        {'state': '/terms/', 'next': DESTINATION},
        HTTP_X_LOGIN_EMAIL='request-auth@example.org',
        secure=True,
    )
    assert response.status_code == 302
    assert response.url == '/terms/'


@pytest.mark.parametrize('age', [86400, 86401])
def test_cross_domain_cancel_requires_unexpired_origin(client, rf, settings, age):
    settings.ALLOWED_HOSTS = ['testserver', 'tickets.example']
    source = rf.get('/event/?lang=en', HTTP_HOST='tickets.example', secure=True)
    return_url = source.build_absolute_uri() + '#speakers'
    with patch('django.core.signing.time.time', return_value=1800000000):
        token = external_link_origin(source)
    with patch('django.core.signing.time.time', return_value=1800000000 + age):
        response = client.get(
            WARNING,
            {'next': DESTINATION, 'return_url': return_url, 'return_origin': token},
            secure=True,
        )
    assert response.status_code == 200
    page = BeautifulSoup(response.content, 'html.parser')
    expected = return_url if age <= 86400 else reverse('presale:index')
    assert page.select_one('[data-external-link-cancel]')['href'] == expected
    assert page.select_one('[data-external-link-continue]')['href'] == DESTINATION
