import pytest
import requests
from django.core.files.base import ContentFile

from eventyay.base.services import http
from eventyay.features.integrations.platforms.storage import nanocdn


@pytest.fixture
def storage(settings):
    settings.NANOCDN_URL = 'https://cdn.example.com/'
    return nanocdn.NanoCDNStorage()


def test_save_uses_the_long_upload_timeout(storage, monkeypatch):
    """The upload body is sent under the connect timeout, so it must not be the short default."""
    captured = {}

    def fake_put(url, **kwargs):
        captured.update(kwargs)
        resp = requests.Response()
        resp.status_code = 201
        resp.headers['Location'] = '/pub/logo.abc.png'
        return resp

    monkeypatch.setattr(http, 'put', fake_put)
    storage._save('pub/logo.png', ContentFile(b'data'))

    assert captured['timeout'] == nanocdn.CDN_UPLOAD_TIMEOUT
    assert captured['timeout'][0] >= 60
