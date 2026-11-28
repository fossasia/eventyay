import pytest
from django.test import RequestFactory

from eventyay.helpers.http import get_client_ip


@pytest.fixture
def proxy_settings(settings):
    settings.TRUST_X_FORWARDED_FOR = True
    settings.TRUSTED_PROXY_COUNT = 1
    return settings


def client_ip(forwarded_for=None):
    headers = {'REMOTE_ADDR': '10.0.0.1'}
    if forwarded_for is not None:
        headers['HTTP_X_FORWARDED_FOR'] = forwarded_for
    return get_client_ip(RequestFactory().get('/', **headers))


def test_uses_address_appended_by_own_proxy(proxy_settings):
    assert client_ip('192.0.2.1') == '192.0.2.1'


def test_ignores_address_sent_by_client(proxy_settings):
    assert client_ip('203.0.113.9, 192.0.2.1') == '192.0.2.1'


def test_two_trusted_proxies(proxy_settings):
    proxy_settings.TRUSTED_PROXY_COUNT = 2
    assert client_ip('203.0.113.9, 192.0.2.1, 198.51.100.7') == '192.0.2.1'


def test_more_trusted_proxies_than_entries(proxy_settings):
    proxy_settings.TRUSTED_PROXY_COUNT = 3
    assert client_ip('192.0.2.1, 198.51.100.7') == '192.0.2.1'


def test_ipv6_address(proxy_settings):
    assert client_ip('203.0.113.9, 2001:db8::1') == '2001:db8::1'


def test_invalid_entry_falls_back_to_remote_addr(proxy_settings):
    assert client_ip('192.0.2.1, not-an-ip') == '10.0.0.1'


def test_without_header_uses_remote_addr(proxy_settings):
    assert client_ip() == '10.0.0.1'


def test_header_ignored_when_not_trusted(proxy_settings):
    proxy_settings.TRUST_X_FORWARDED_FOR = False
    assert client_ip('192.0.2.1') == '10.0.0.1'
