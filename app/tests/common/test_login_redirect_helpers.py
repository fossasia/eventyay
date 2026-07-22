import json
from http import HTTPStatus
from unittest.mock import MagicMock

from django.http import HttpResponseRedirect, JsonResponse

from eventyay.common.views.helpers import (
    build_login_url_with_next,
    is_ajax_request,
    login_redirect_with_next,
    redirect_or_json_redirect,
)


def test_is_ajax_request_detects_xhr_header():
    request = MagicMock()
    request.headers = {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'text/html'}
    assert is_ajax_request(request) is True


def test_is_ajax_request_detects_json_accept():
    request = MagicMock()
    request.headers = {'Accept': 'application/json'}
    assert is_ajax_request(request) is True


def test_is_ajax_request_false_for_normal_browser_get():
    request = MagicMock()
    request.headers = {'Accept': 'text/html'}
    assert is_ajax_request(request) is False


def test_login_redirect_with_next_browser_redirect(rf):
    request = rf.get('/wm/wikimania2026/online-video/join/')
    response = login_redirect_with_next(request)

    assert isinstance(response, HttpResponseRedirect)
    assert response.url.startswith('/common/login/')
    assert 'next=' in response.url
    assert 'online-video%2Fjoin' in response.url or 'online-video/join' in response.url


def test_login_redirect_with_next_ajax_returns_login_url(rf):
    request = rf.get(
        '/wm/wikimania2026/online-video/join/',
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )
    response = login_redirect_with_next(request)

    assert isinstance(response, JsonResponse)
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    payload = json.loads(response.content.decode())
    assert 'login_url' in payload
    assert payload['login_url'].startswith('/common/login/')
    assert 'next=' in payload['login_url']


def test_build_login_url_with_next():
    url = build_login_url_with_next('/wm/event/online-video/join/')
    assert url.startswith('/common/login/')
    assert 'next=' in url


def test_redirect_or_json_redirect_ajax(rf):
    request = rf.get('/join/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    response = redirect_or_json_redirect(request, 'https://video.example/#token=abc')
    assert isinstance(response, JsonResponse)
    assert json.loads(response.content.decode())['redirect_url'] == 'https://video.example/#token=abc'


def test_redirect_or_json_redirect_browser(rf):
    request = rf.get('/join/')
    response = redirect_or_json_redirect(request, 'https://video.example/#token=abc')
    assert isinstance(response, HttpResponseRedirect)
    assert response.url == 'https://video.example/#token=abc'
