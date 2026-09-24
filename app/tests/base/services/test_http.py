from unittest import mock
from unittest.mock import patch

import pytest

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
