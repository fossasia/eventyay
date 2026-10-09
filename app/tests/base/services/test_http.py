import socket
import time
from unittest.mock import patch

import pytest
import requests

from eventyay.base.services import http


@pytest.mark.parametrize(
    ('helper', 'method', 'extra'),
    [
        (http.get, 'GET', {}),
        (http.post, 'POST',{}),
        (http.put, 'PUT', {}),
        (http.delete, 'DELETE', {}),
        (http.head, 'HEAD', {'allow_redirects': False}),
    ],
)
def test_helper_applies_default_timeout(helper, method, extra):
    """Every verb helper must apply DEFAULT_TIMEOUT when the caller omits one."""
    with patch('eventyay.base.services.http.requests.request') as mocked:
        helper('https://example.com/hook')

    mocked.assert_called_once_with(method, 'https://example.com/hook', timeout=http.DEFAULT_TIMEOUT, **extra)


def test_helper_respects_explicit_timeout_override():
    """A caller-supplied timeout must win over the default."""
    with patch('eventyay.base.services.http.requests.request') as mocked:
        http.post('https://example.com/hook', json={'a': 1}, timeout=5)

    mocked.assert_called_once_with('POST', 'https://example.com/hook', json={'a': 1}, timeout=5)


def test_helper_forwards_other_kwargs_untouched():
    """Non-timeout kwargs (json, headers, allow_redirects, ...) must pass through unchanged."""
    with patch('eventyay.base.services.http.requests.request') as mocked:
        http.post(
            'https://example.com/hook',
            json={'foo': 'bar'},
            headers={'X-Test': '1'},
            allow_redirects=False,
        )

    mocked.assert_called_once_with(
        'POST',
        'https://example.com/hook',
        json={'foo': 'bar'},
        headers={'X-Test': '1'},
        allow_redirects=False,
        timeout=http.DEFAULT_TIMEOUT,
    )


def test_request_dispatches_to_requests_request():
    """The generic ``request`` entrypoint forwards the method name verbatim."""
    with patch('eventyay.base.services.http.requests.request') as mocked:
        http.request('PATCH', 'https://example.com/hook')

    mocked.assert_called_once_with('PATCH', 'https://example.com/hook', timeout=http.DEFAULT_TIMEOUT)

@patch('eventyay.base.services.http.requests.request')
def test_head_does_not_follow_redirects_by_default(mock_request):
    http.head('https://example.com')
    assert mock_request.call_args.kwargs['allow_redirects'] is False


@patch('eventyay.base.services.http.requests.request')
def test_head_redirect_default_can_be_overridden(mock_request):
    http.head('https://example.com', allow_redirects=True)
    assert mock_request.call_args.kwargs['allow_redirects'] is True


@pytest.fixture
def stalled_server(monkeypatch):
    """A local server that accepts connections but never sends a response."""
    monkeypatch.setenv('NO_PROXY', '127.0.0.1')
    monkeypatch.setenv('no_proxy', '127.0.0.1')
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    try:
        yield f'http://127.0.0.1:{server.getsockname()[1]}/'
    finally:
        server.close()


def test_stalled_endpoint_raises_timeout_with_explicit_override(stalled_server):
    """A silent endpoint must raise a timeout instead of blocking forever."""
    start = time.monotonic()
    with pytest.raises(requests.exceptions.Timeout):
        http.get(stalled_server, timeout=(1, 0.5))
    assert time.monotonic() - start < 5


def test_stalled_endpoint_raises_timeout_with_default(stalled_server, monkeypatch):
    """The default timeout alone (no caller override) must also bound a stalled call."""
    monkeypatch.setattr(http, 'DEFAULT_TIMEOUT', (1, 0.5))
    start = time.monotonic()
    with pytest.raises(requests.exceptions.Timeout):
        http.post(stalled_server, json={'ping': 'pong'})
    assert time.monotonic() - start < 5
