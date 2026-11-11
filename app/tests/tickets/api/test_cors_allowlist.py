from corsheaders.middleware import CorsMiddleware
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory

from eventyay.control.checkin_app import CHECKIN_APP_PRODUCTION_URL


def cors_response(path, origin, method='OPTIONS'):
    middleware = CorsMiddleware(lambda request: HttpResponse('ok'))
    extra = {}
    if method == 'OPTIONS':
        extra['HTTP_ACCESS_CONTROL_REQUEST_METHOD'] = 'GET'
        extra['HTTP_ACCESS_CONTROL_REQUEST_HEADERS'] = 'authorization'
    request = RequestFactory().generic(method, path, HTTP_ORIGIN=origin, **extra)
    return middleware(request)


def test_checkin_origin_is_an_explicit_allowlist():
    assert settings.CORS_ALLOW_ALL_ORIGINS is False
    assert settings.CORS_ALLOW_CREDENTIALS is False
    assert settings.CORS_URLS_REGEX == r'^/api/v1/'
    assert settings.CORS_ALLOWED_ORIGINS[0] == CHECKIN_APP_PRODUCTION_URL.rstrip('/')
    assert '*' not in settings.CORS_ALLOWED_ORIGINS


def test_api_preflight_echoes_checkin_origin():
    response = cors_response('/api/v1/organizers/', 'https://access.eventyay.com')
    assert response.status_code == 200
    assert response['Access-Control-Allow-Origin'] == 'https://access.eventyay.com'
    assert 'authorization' in response['Access-Control-Allow-Headers']
    assert 'Access-Control-Allow-Credentials' not in response


def test_api_get_echoes_checkin_origin():
    response = cors_response('/api/v1/organizers/', 'https://access.eventyay.com', method='GET')
    assert response['Access-Control-Allow-Origin'] == 'https://access.eventyay.com'
    assert response.content == b'ok'


def test_api_preflight_rejects_unknown_origin():
    response = cors_response('/api/v1/organizers/', 'https://evil.example')
    assert 'Access-Control-Allow-Origin' not in response


def test_allowlist_does_not_cover_other_routes():
    for path in ('/login/', '/organizer/event/widget/aaaaaaaaaaaaaaaa/'):
        response = cors_response(path, 'https://access.eventyay.com')
        assert 'Access-Control-Allow-Origin' not in response


def test_extra_origins_come_from_configuration(settings):
    assert settings.CORS_ALLOWED_ORIGINS[0] == 'https://access.eventyay.com'
    assert not any(origin.startswith('http://localhost') for origin in settings.CORS_ALLOWED_ORIGINS)


def test_event_permission_middleware_does_not_add_wildcard_cors_to_api():
    from django.contrib.auth.models import AnonymousUser

    from eventyay.common.middleware.event import EventPermissionMiddleware

    middleware = EventPermissionMiddleware(lambda request: HttpResponse('ok'))
    request = RequestFactory().get('/api/v1/organizers/')
    request.user = AnonymousUser()
    response = middleware(request)
    assert 'Access-Control-Allow-Origin' not in response


