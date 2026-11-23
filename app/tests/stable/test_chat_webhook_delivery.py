import hashlib
import hmac
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock

import pytest
import requests

from eventyay.features.live import tasks
from eventyay.storage import external


PUBLIC_IP = '93.184.216.34'
PAYLOAD = {'type': 'chat.message', 'content': {'body': 'hello'}}
SECRET = 'webhook-secret'


def resolve_to(mapping):
    """Fake getaddrinfo that resolves each hostname to the given addresses."""

    def getaddrinfo(host, port, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror('unknown host')
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (addr, port)) for addr in mapping[host]]

    return getaddrinfo


@pytest.fixture
def dns(monkeypatch, settings):
    settings.DEBUG = False
    mapping = {'hooks.example': [PUBLIC_IP]}
    monkeypatch.setattr(external.socket, 'getaddrinfo', resolve_to(mapping))
    return mapping


@pytest.fixture
def send_pinned(monkeypatch):
    response = MagicMock(status_code=200)
    send = MagicMock(return_value=response)
    monkeypatch.setattr(tasks, 'send_pinned', send)
    return send


@pytest.fixture
def logged_events(monkeypatch):
    events = []
    monkeypatch.setattr(tasks, 'log_event', lambda *args, **kwargs: events.append((args, kwargs)))
    return events


@pytest.mark.parametrize('address', ['127.0.0.1', '10.0.0.5', '169.254.169.254', '::1'])
def test_private_address_at_send_time_is_not_requested(dns, send_pinned, logged_events, address):
    # The URL passed the check when it was saved, but now resolves to a private address.
    dns['hooks.example'] = [address]
    tasks.send_chat_webhook(PAYLOAD, 'https://hooks.example/chat', SECRET)
    send_pinned.assert_not_called()
    assert logged_events[0][1]['error_code'] == 'blocked_url'


def test_unresolvable_host_is_not_requested(dns, send_pinned, logged_events):
    tasks.send_chat_webhook(PAYLOAD, 'https://gone.example/chat', SECRET)
    send_pinned.assert_not_called()
    assert logged_events[0][1]['error_code'] == 'blocked_url'


def test_public_address_is_requested_at_the_checked_address(dns, send_pinned, logged_events):
    tasks.send_chat_webhook(PAYLOAD, 'https://hooks.example/chat', SECRET)
    send_pinned.assert_called_once()
    _, request, addresses, timeout = send_pinned.call_args.args
    assert addresses == (PUBLIC_IP,)
    assert timeout == tasks.WEBHOOK_TIMEOUT
    assert request.method == 'POST'
    assert request.url == 'https://hooks.example/chat'
    body = json.dumps(PAYLOAD, separators=(',', ':'), sort_keys=True)
    assert request.body == body
    expected = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    assert request.headers['X-Eventyay-Signature'] == f'sha256={expected}'
    assert logged_events[0][0][2] == tasks.OUTCOME_SUCCESS


def test_webhook_is_posted_to_pinned_address_without_resolving_again(monkeypatch, settings):
    settings.DEBUG = False
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received['host'] = self.headers['Host']
            received['signature'] = self.headers['X-Eventyay-Signature']
            received['body'] = self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(('127.0.0.1', 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # The address check passed for this address; any later lookup of the hostname
    # (e.g. a rebinding DNS answer) must not be used.
    monkeypatch.setattr(tasks, 'resolve_public_addresses', lambda url: ('127.0.0.1',))
    real_getaddrinfo = socket.getaddrinfo

    def no_dns(host, *args, **kwargs):
        if host != '127.0.0.1':
            raise AssertionError(f'hostname {host} was resolved again')
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, 'getaddrinfo', no_dns)
    try:
        response = tasks.post_webhook(f'http://hooks.example:{port}/chat', b'{"a":1}', {'X-Eventyay-Signature': 'sig'})
    finally:
        server.shutdown()
        server.server_close()

    assert response.status_code == 204
    assert received == {'host': f'hooks.example:{port}', 'signature': 'sig', 'body': b'{"a":1}'}


def test_debug_allows_private_targets(monkeypatch, settings):
    settings.DEBUG = True
    post = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr(tasks.requests, 'post', post)
    tasks.post_webhook('http://localhost:9000/chat', b'{}', {})
    post.assert_called_once()
    assert post.call_args.kwargs['allow_redirects'] is False


class IPv6HTTPServer(HTTPServer):
    address_family = socket.AF_INET6


def serve_on(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def stop(*servers):
    for server in servers:
        server.shutdown()
        server.server_close()


class RecordingHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        self.received.append(self.rfile.read(int(self.headers['Content-Length'])))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_post_is_not_resent_after_connection_breaks(monkeypatch, settings):
    """If the first address takes the POST and drops the connection, the next one gets nothing."""
    settings.DEBUG = False
    first_received = []

    class DropHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            first_received.append(self.rfile.read(int(self.headers['Content-Length'])))
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)

        def log_message(self, *args):
            pass

    RecordingHandler.received = []
    second = serve_on(IPv6HTTPServer(('::1', 0), RecordingHandler))
    port = second.server_address[1]
    first = serve_on(HTTPServer(('127.0.0.1', port), DropHandler))
    monkeypatch.setattr(tasks, 'resolve_public_addresses', lambda url: ('127.0.0.1', '::1'))
    try:
        with pytest.raises(requests.ConnectionError):
            tasks.post_webhook(f'http://hooks.example:{port}/chat', b'{"a":1}', {})
    finally:
        stop(first, second)

    assert first_received == [b'{"a":1}']
    assert RecordingHandler.received == []


def test_post_moves_on_when_connection_is_refused(monkeypatch, settings):
    settings.DEBUG = False
    RecordingHandler.received = []
    second = serve_on(IPv6HTTPServer(('::1', 0), RecordingHandler))
    port = second.server_address[1]
    # Nothing listens on 127.0.0.1 at this port, so the connection is refused.
    monkeypatch.setattr(tasks, 'resolve_public_addresses', lambda url: ('127.0.0.1', '::1'))
    try:
        response = tasks.post_webhook(f'http://hooks.example:{port}/chat', b'{"a":1}', {})
    finally:
        stop(second)

    assert response.status_code == 200
    assert RecordingHandler.received == [b'{"a":1}']
