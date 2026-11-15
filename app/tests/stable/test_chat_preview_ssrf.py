import socket
from unittest.mock import MagicMock

import pytest

from eventyay.storage import external
from eventyay.storage.external import is_public_http_url, retrieve_url


PUBLIC_IP = '93.184.216.34'


def resolve_to(mapping):
    """Fake getaddrinfo that resolves each hostname to the given addresses."""

    def getaddrinfo(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror('unknown host')
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (addr, port)) for addr in mapping[host]]

    return getaddrinfo


def fake_response(status_code=200, location=None):
    response = MagicMock()
    response.status_code = status_code
    response.is_redirect = location is not None
    response.headers = {'Location': location} if location else {}
    return response


@pytest.fixture
def dns(monkeypatch):
    mapping = {'public.example': [PUBLIC_IP]}
    monkeypatch.setattr(external.socket, 'getaddrinfo', resolve_to(mapping))
    return mapping


@pytest.fixture
def http_get(monkeypatch):
    get = MagicMock(return_value=fake_response())
    monkeypatch.setattr(external.requests, 'get', get)
    return get


@pytest.mark.parametrize(
    'addresses',
    [
        ['127.0.0.1'],
        ['10.0.0.5'],
        ['192.168.1.1'],
        ['169.254.169.254'],
        ['::1'],
        ['fd00::1'],
        ['::ffff:127.0.0.1'],
        ['0.0.0.0'],
        [PUBLIC_IP, '10.0.0.5'],
    ],
)
def test_non_public_addresses_are_refused(dns, addresses):
    dns['internal.example'] = addresses
    assert not is_public_http_url('http://internal.example/')


@pytest.mark.parametrize(
    'url',
    [
        'file:///etc/passwd',
        'ftp://public.example/',
        'http:///no-host',
        'http://unknown.example/',
        'http://public.example:99999/',
    ],
)
def test_invalid_urls_are_refused(dns, url):
    assert not is_public_http_url(url)


def test_public_url_is_allowed(dns):
    assert is_public_http_url('https://public.example/page')


def test_retrieve_url_does_not_request_private_hosts(dns, http_get):
    dns['internal.example'] = ['10.0.0.5']
    assert retrieve_url('http://internal.example/admin') is None
    http_get.assert_not_called()


def test_retrieve_url_fetches_public_url_without_auto_redirects(dns, http_get):
    assert retrieve_url('https://public.example/page') is http_get.return_value
    http_get.assert_called_once()
    assert http_get.call_args.kwargs['allow_redirects'] is False


def test_retrieve_url_blocks_redirect_to_private_host(dns, http_get):
    dns['internal.example'] = ['169.254.169.254']
    http_get.return_value = fake_response(302, 'http://internal.example/latest/meta-data/')
    assert retrieve_url('https://public.example/page') is None
    http_get.assert_called_once()


def test_retrieve_url_follows_public_relative_redirect(dns, http_get):
    final = fake_response()
    http_get.side_effect = [fake_response(301, '/new'), final]
    assert retrieve_url('https://public.example/old') is final
    assert http_get.call_args.args[0] == 'https://public.example/new'


def test_retrieve_url_limits_redirects(dns, http_get):
    http_get.return_value = fake_response(302, 'https://public.example/loop')
    assert retrieve_url('https://public.example/loop') is None
    assert http_get.call_count == external.MAX_PREVIEW_REDIRECTS + 1
