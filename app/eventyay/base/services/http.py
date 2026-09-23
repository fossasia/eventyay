"""
Shared outbound-HTTP helper.

``requests`` does not apply any timeout by default, which means a call can
hang forever if the remote server accepts the TCP connection but never
sends a response. Several outbound calls in this codebase run inside
Celery tasks (some with ``acks_late=True``), so a single unresponsive
third party can occupy a worker indefinitely.

Use ``get`` / ``post`` / ``put`` / ``delete`` / ``head`` from this module
instead of calling ``requests`` directly, so every outbound call gets a
sane default timeout unless the caller explicitly overrides it.
"""

import requests

# (connect timeout, read timeout) in seconds. Generous enough for slow but
# healthy third parties, short enough that a Celery worker is never blocked
# indefinitely by a single hung request.
DEFAULT_TIMEOUT = (5, 30)


def request(method: str, url: str, **kwargs):
    """Call ``requests.request`` with a default timeout applied.

    Any ``timeout`` passed explicitly by the caller takes precedence, so
    call sites that need a different value (e.g. large file transfers)
    remain free to set their own.
    """
    kwargs.setdefault('timeout', DEFAULT_TIMEOUT)
    return requests.request(method, url, **kwargs)


def get(url: str, **kwargs):
    return request('GET', url, **kwargs)


def post(url: str, **kwargs):
    return request('POST', url, **kwargs)


def put(url: str, **kwargs):
    return request('PUT', url, **kwargs)


def delete(url: str, **kwargs):
    return request('DELETE', url, **kwargs)


def head(url: str, **kwargs):
    return request('HEAD', url, **kwargs)
