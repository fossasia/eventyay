import pytest
import requests

from eventyay.base.services import http
from eventyay.features.integrations.platforms.storage.nanocdn import NanoCDNStorage


def _head_response(content_length):
    resp = requests.Response()
    resp.status_code = 200
    if content_length is not None:
        resp.headers['Content-Length'] = content_length
    return resp


@pytest.fixture
def storage(settings):
    settings.NANOCDN_URL = 'https://cdn.example.com/'
    return NanoCDNStorage()


def test_size_returns_content_length(storage, monkeypatch):
    monkeypatch.setattr(http, 'head', lambda url, **kwargs: _head_response('1234'))
    assert storage.size('pub/file.png') == 1234


@pytest.mark.parametrize('value', ['-1', 'abc', '', None])
def test_size_rejects_invalid_content_length(storage, monkeypatch, value):
    """Missing, non-numeric, or negative Content-Length must raise OSError, not return garbage."""
    monkeypatch.setattr(http, 'head', lambda url, **kwargs: _head_response(value))
    with pytest.raises(OSError):
        storage.size('pub/file.png')
