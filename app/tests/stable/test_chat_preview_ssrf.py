import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict

from eventyay.storage import external
from eventyay.storage.external import PinnedAddressAdapter, fetch_pinned, resolve_public_addresses, retrieve_url


PUBLIC_IP = '93.184.216.34'


def resolve_to(mapping):
    """Fake getaddrinfo that resolves each hostname to the given addresses."""

    def getaddrinfo(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror('unknown host')
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (addr, port)) for addr in mapping[host]]

    return getaddrinfo


def fake_response(status_code=200, location=None, body=b'<html></html>', headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.is_redirect = location is not None
    response.headers = CaseInsensitiveDict({'Location': location} if location else headers or {})
    response.url = 'https://public.example/final'
    response.iter_content.return_value = [body]
    response.__enter__.return_value = response
    return response


@pytest.fixture
def dns(monkeypatch):
    mapping = {'public.example': [PUBLIC_IP]}
    monkeypatch.setattr(external.socket, 'getaddrinfo', resolve_to(mapping))
    return mapping


@pytest.fixture
def http_get(monkeypatch):
    get = MagicMock(return_value=fake_response())
    monkeypatch.setattr(external, 'fetch_pinned', get)
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
        ['64:ff9b::a00:5'],  # NAT64 for 10.0.0.5
        ['64:ff9b::7f00:1'],  # NAT64 for 127.0.0.1
        ['2002:7f00:1::'],  # 6to4 for 127.0.0.1
        ['0.0.0.0'],
        ['224.0.0.1'],
        ['fec0::1'],  # site-local, reported as global by Python 3.12
        [PUBLIC_IP, '10.0.0.5'],
    ],
)
def test_non_public_addresses_are_refused(dns, addresses):
    dns['internal.example'] = addresses
    assert resolve_public_addresses('http://internal.example/') == ()


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
    assert resolve_public_addresses(url) == ()


def test_public_url_returns_resolved_address(dns):
    assert resolve_public_addresses('https://public.example/page') == (PUBLIC_IP,)


def test_nat64_of_public_address_is_allowed(dns):
    dns['nat64.example'] = ['64:ff9b::5db8:d822']  # NAT64 for 93.184.216.34
    assert resolve_public_addresses('https://nat64.example/') == ('64:ff9b::5db8:d822',)


def test_slow_dns_is_refused(monkeypatch):
    def slow_getaddrinfo(*args, **kwargs):
        time.sleep(1)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (PUBLIC_IP, 80))]

    monkeypatch.setattr(external.socket, 'getaddrinfo', slow_getaddrinfo)
    monkeypatch.setattr(external, 'PREVIEW_DNS_TIMEOUT', 0.05)
    assert resolve_public_addresses('http://slow.example/') == ()


def test_retrieve_url_does_not_request_private_hosts(dns, http_get):
    dns['internal.example'] = ['10.0.0.5']
    assert retrieve_url('http://internal.example/admin') is None
    http_get.assert_not_called()


def test_retrieve_url_requests_the_validated_address(dns, http_get):
    assert retrieve_url('https://public.example/page').content == b'<html></html>'
    assert http_get.call_args.args[1:] == ('https://public.example/page', (PUBLIC_IP,))


def test_retrieve_url_blocks_redirect_to_private_host(dns, http_get):
    dns['internal.example'] = ['169.254.169.254']
    http_get.return_value = fake_response(302, 'http://internal.example/latest/meta-data/')
    assert retrieve_url('https://public.example/page') is None
    http_get.assert_called_once()


def test_retrieve_url_follows_public_relative_redirect(dns, http_get):
    final = fake_response(body=b'new')
    http_get.side_effect = [fake_response(301, '/new'), final]
    assert retrieve_url('https://public.example/old').content == b'new'
    assert http_get.call_args.args[1:] == ('https://public.example/new', (PUBLIC_IP,))


def test_retrieve_url_limits_redirects(dns, http_get):
    http_get.return_value = fake_response(302, 'https://public.example/loop')
    assert retrieve_url('https://public.example/loop') is None
    assert http_get.call_count == external.MAX_PREVIEW_REDIRECTS + 1


def test_fetch_pinned_connects_to_address_without_resolving_hostname(monkeypatch):
    """The hostname is never resolved again; the Host header keeps the original name."""
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen['host'] = self.headers['Host']
            seen['path'] = self.path
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'ok')

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    real_getaddrinfo = socket.getaddrinfo

    def no_dns(host, *args, **kwargs):
        # urllib3 passes the IP literal to getaddrinfo, which needs no DNS lookup.
        if host != '127.0.0.1':
            raise AssertionError(f'{host} must not be resolved again')
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, 'getaddrinfo', no_dns)
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = fetch_pinned(session, f'http://rebind.example:{port}/page?x=1', ['127.0.0.1'])
    finally:
        server.shutdown()
        server.server_close()

    assert response.status_code == 200
    assert response.content == b'ok'
    assert response.url == f'http://rebind.example:{port}/page?x=1'
    assert seen == {'host': f'rebind.example:{port}', 'path': '/page?x=1'}


def test_pinned_adapter_keeps_hostname_for_tls():
    """For https the certificate and SNI are checked against the original hostname."""
    adapter = PinnedAddressAdapter('2001:db8::1')
    request = requests.Request('GET', 'https://public.example/page').prepare()
    with patch.object(HTTPAdapter, 'send', return_value=MagicMock()) as send:
        response = adapter.send(request)

    sent = send.call_args.args[0]
    assert sent.url == 'https://[2001:db8::1]/page'
    assert sent.headers['Host'] == 'public.example'
    assert request.url == 'https://public.example/page'
    assert response.request is request
    assert adapter.poolmanager.connection_pool_kw['server_hostname'] == 'public.example'
    assert adapter.poolmanager.connection_pool_kw['assert_hostname'] == 'public.example'
    assert response.url == 'https://public.example/page'


def test_validated_hostname_is_the_requested_hostname(dns, http_get):
    """Python and Requests encode non-ASCII hostnames differently; the requested one is checked."""
    dns['xn--fa-hia.attacker.example'] = [PUBLIC_IP]  # what Requests sends for faß
    dns['fass.attacker.example'] = ['127.0.0.1']  # what getaddrinfo would use for faß
    assert retrieve_url('http://faß.attacker.example/') is not None
    assert http_get.call_args.args[1:] == ('http://xn--fa-hia.attacker.example/', (PUBLIC_IP,))

    dns['xn--fa-hia.attacker.example'] = ['127.0.0.1']
    dns['fass.attacker.example'] = [PUBLIC_IP]
    http_get.reset_mock()
    assert retrieve_url('http://faß.attacker.example/') is None
    http_get.assert_not_called()


def test_cookies_are_kept_across_redirects(monkeypatch):
    """A cookie set before a redirect is sent with the redirected request."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/start':
                self.send_response(302)
                self.send_header('Set-Cookie', 'consent=yes; Path=/')
                self.send_header('Location', '/article')
            elif 'consent=yes' in (self.headers['Cookie'] or ''):
                self.send_response(200)
            else:
                self.send_response(403)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(external, 'resolve_public_addresses', lambda url: ('127.0.0.1',))
    try:
        response = retrieve_url(f'http://cookie.example:{port}/start')
    finally:
        server.shutdown()
        server.server_close()

    assert response is not None
    assert response.url == f'http://cookie.example:{port}/article'


def test_retrieve_url_blocks_redirect_to_site_local_host(dns, http_get):
    dns['sitelocal.example'] = ['fec0::1']
    http_get.return_value = fake_response(302, 'http://sitelocal.example/')
    assert retrieve_url('https://public.example/page') is None
    http_get.assert_called_once()


@pytest.mark.parametrize('literal', ['fec0::1', '2002:7f00:1::', '2002:5db8:d822::'])
def test_retrieve_url_blocks_ipv6_literals(dns, http_get, literal):
    """IP literals resolve to themselves, so the address check itself must refuse them."""
    dns[literal] = [literal]
    assert retrieve_url(f'http://[{literal}]/') is None
    http_get.assert_not_called()


def serve(handler_class):
    server = HTTPServer(('127.0.0.1', 0), handler_class)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_fetch_pinned_falls_back_to_next_validated_address(monkeypatch):
    """If the first validated address refuses the connection, the next one is used."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    original_send = PinnedAddressAdapter.send

    def send(self, request, **kwargs):
        if self.address == '192.0.2.1':
            raise requests.ConnectionError('unreachable')
        return original_send(self, request, **kwargs)

    monkeypatch.setattr(PinnedAddressAdapter, 'send', send)
    server = serve(Handler)
    try:
        with requests.Session() as session:
            session.trust_env = False
            url = f'http://multi.example:{server.server_address[1]}/'
            response = fetch_pinned(session, url, ['192.0.2.1', '127.0.0.1'])
            assert response.status_code == 200
            with pytest.raises(requests.ConnectionError):
                fetch_pinned(session, url, ['192.0.2.1'])
    finally:
        server.shutdown()
        server.server_close()


def test_utf8_redirect_target_is_decoded(monkeypatch):
    """A UTF-8 Location header is decoded like Requests does before it is followed."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            if self.path == '/start':
                self.send_response(302)
                self.send_header('Location', '/café'.encode().decode('latin-1'))
            else:
                self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    monkeypatch.setattr(external, 'resolve_public_addresses', lambda url: ('127.0.0.1',))
    server = serve(Handler)
    try:
        response = retrieve_url(f'http://utf8.example:{server.server_address[1]}/start')
    finally:
        server.shutdown()
        server.server_close()

    assert response is not None
    assert seen == ['/start', '/caf%C3%A9']


def test_retrieve_url_returns_final_url_headers_and_body(dns, http_get):
    http_get.return_value = fake_response(body=b'<html>hi</html>', headers={'Content-Type': 'text/html'})
    result = retrieve_url('https://public.example/page')
    assert result == external.PreviewResponse(
        url='https://public.example/final',
        headers=http_get.return_value.headers,
        content=b'<html>hi</html>',
    )
    assert http_get.return_value.headers['Content-Type'] == 'text/html'


def test_retrieve_url_refuses_body_over_the_limit(dns, http_get, settings):
    """The body is streamed and refused once it exceeds the upload limit."""
    settings.MAX_SIZE_CONFIG = {**settings.MAX_SIZE_CONFIG, external.SizeKey.UPLOAD_SIZE_OTHER: 10}
    big = fake_response()
    big.iter_content.return_value = iter([b'x' * 8, b'x' * 8, b'never read'])
    http_get.return_value = big
    assert retrieve_url('https://public.example/big.png') is None

    http_get.return_value = fake_response(body=b'x' * 10)
    assert retrieve_url('https://public.example/ok.png').content == b'x' * 10


def test_retrieve_url_refuses_large_content_length_without_reading(dns, http_get, settings):
    settings.MAX_SIZE_CONFIG = {**settings.MAX_SIZE_CONFIG, external.SizeKey.UPLOAD_SIZE_OTHER: 10}
    http_get.return_value = fake_response(headers={'Content-Length': '11'})
    assert retrieve_url('https://public.example/big.png') is None
    http_get.return_value.iter_content.assert_not_called()


def test_fetch_pinned_streams_the_body(dns, monkeypatch):
    send = MagicMock(return_value=MagicMock(raw=None))
    monkeypatch.setattr(HTTPAdapter, 'send', send)
    with requests.Session() as session:
        fetch_pinned(session, 'https://public.example/', [PUBLIC_IP])
    assert send.call_args.kwargs['stream'] is True


def test_redirect_body_is_not_read(monkeypatch):
    """
    A redirect announcing a huge body that never completes is followed without reading it.
    ``Session.send`` would read the whole redirect body even with stream=True.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/start':
                self.send_response(302)
                self.send_header('Location', '/final')
                self.send_header('Content-Length', str(10**9))
                self.end_headers()
                self.wfile.write(b'x' * 1024)
                self.wfile.flush()
                time.sleep(3)  # Never finishes the announced body
            else:
                self.send_response(200)
                self.send_header('Content-Length', '4')
                self.end_headers()
                self.wfile.write(b'done')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    server.block_on_close = False
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(external, 'resolve_public_addresses', lambda url: ('127.0.0.1',))
    monkeypatch.setattr(external, 'PREVIEW_HTTP_TIMEOUT', 1)
    try:
        start = time.monotonic()
        response = retrieve_url(f'http://redirect.example:{server.server_address[1]}/start')
        elapsed = time.monotonic() - start
    finally:
        server.shutdown()
        server.server_close()

    assert response is not None
    assert response.content == b'done'
    assert elapsed < 1
