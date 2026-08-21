from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest


def test_api_404_does_not_render_template(monkeypatch):
    from django.http import Http404
    from django.test import RequestFactory

    from eventyay.base.views.errors import page_not_found

    get_template = MagicMock()
    monkeypatch.setattr('eventyay.base.views.errors.get_template', get_template)
    response = page_not_found(RequestFactory().get('/api/v1/does-not-exist'), Http404())
    assert response.status_code == 404
    get_template.assert_not_called()


def test_html_404_still_renders_template(monkeypatch):
    from django.http import Http404
    from django.test import RequestFactory

    from eventyay.base.views.errors import page_not_found

    template = MagicMock()
    template.render.return_value = '<html>404</html>'
    monkeypatch.setattr('eventyay.base.views.errors.get_template', lambda name: template)
    response = page_not_found(RequestFactory().get('/missing-page'), Http404())
    assert response.status_code == 404
    template.render.assert_called_once()


@contextmanager
def overloaded_middleware(monkeypatch):
    from django.http import HttpResponse

    from eventyay.base import middleware as middleware_module
    from eventyay.base.middleware import LoadSheddingMiddleware

    monkeypatch.setattr(middleware_module, 'MAX_CONCURRENT_REQUESTS', 16)
    previous = LoadSheddingMiddleware.active_requests
    LoadSheddingMiddleware.active_requests = 16
    try:
        yield LoadSheddingMiddleware(lambda request: HttpResponse('ok'))
    finally:
        LoadSheddingMiddleware.active_requests = previous


def test_load_shedding_is_enabled_by_default():
    from eventyay.base.middleware import MAX_CONCURRENT_REQUESTS

    assert MAX_CONCURRENT_REQUESTS == 4


def test_load_shedding_can_be_disabled(monkeypatch):
    from django.http import HttpResponse
    from django.test import RequestFactory

    from eventyay.base import middleware as middleware_module
    from eventyay.base.middleware import LoadSheddingMiddleware

    monkeypatch.setattr(middleware_module, 'MAX_CONCURRENT_REQUESTS', 0)
    previous = LoadSheddingMiddleware.active_requests
    LoadSheddingMiddleware.active_requests = 10_000
    try:
        middleware = LoadSheddingMiddleware(lambda request: HttpResponse('ok'))
        assert middleware(RequestFactory().get('/schedule/')).status_code == 200
    finally:
        LoadSheddingMiddleware.active_requests = previous


def test_load_shedding_returns_503(monkeypatch):
    from django.test import RequestFactory

    with overloaded_middleware(monkeypatch) as middleware:
        response = middleware(RequestFactory().get('/schedule/'))
        assert response.status_code == 503
        assert response['Retry-After'] == '10'
        assert response['Content-Type'] == 'application/json'


def test_load_shedding_returns_html_to_browsers(monkeypatch):
    from django.test import RequestFactory

    with overloaded_middleware(monkeypatch) as middleware:
        response = middleware(RequestFactory().get('/schedule/', HTTP_ACCEPT='text/html'))
        assert response.status_code == 503
        assert response['Retry-After'] == '10'
        assert response['Content-Type'] == 'text/plain'


def test_load_shedding_keeps_api_overload_json(monkeypatch):
    from django.test import RequestFactory

    with overloaded_middleware(monkeypatch) as middleware:
        response = middleware(
            RequestFactory().get('/api/v1/organizers/wm/events/wm/schedule/', HTTP_ACCEPT='text/html')
        )
        assert response.status_code == 503
        assert response['Content-Type'] == 'application/json'


@pytest.mark.parametrize(
    'path',
    [
        '/healthcheck/',
        '/api/v1/organizers/wm/checkin/redeem/',
        '/api/v1/organizers/wm/events/wm/checkinlists/',
        '/api/v1/organizers/wm/events/wm/checkinlists/1/positions/',
    ],
)
def test_load_shedding_exempts_checkin_and_health(path, monkeypatch):
    from django.test import RequestFactory

    with overloaded_middleware(monkeypatch) as middleware:
        assert middleware(RequestFactory().get(path)).status_code == 200


@pytest.mark.parametrize(
    'path',
    [
        '/schedule/',
        '/api/v1/organizers/wm/events/wm/checkinlists-backup/',
    ],
)
def test_load_shedding_does_not_exempt_unrelated_paths(path, monkeypatch):
    from django.test import RequestFactory

    with overloaded_middleware(monkeypatch) as middleware:
        assert middleware(RequestFactory().get(path)).status_code == 503


def test_heavy_celery_tasks_routed_to_longrunning():
    from django.conf import settings

    routes = settings.CELERY_TASK_ROUTES
    for name in (
        'eventyay.plugins.badges.tasks.*',
        'eventyay.base.services.export.*',
        'eventyay.base.services.orderimport.*',
        'eventyay.features.importers.tasks.*',
        'eventyay.base.services.tickets.generate',
        'eventyay.base.services.tickets.invalidate_cache',
        'pretalx.agenda.export_schedule_html',
    ):
        assert routes[name]['queue'] == 'longrunning'


def test_badge_async_fallback_uses_tickets_generate_task():
    from eventyay.base.services.tickets import generate
    from eventyay.plugins.badges import api as badges_api

    assert badges_api.generate is generate
    assert hasattr(generate, 'apply_async')


def test_404_skips_session_save():
    from django.http import HttpResponse
    from django.test import RequestFactory

    from eventyay.common.middleware.domains import SessionMiddleware

    saved = []

    class FakeSession:
        accessed = True
        modified = False

        def is_empty(self):
            return False

        def save(self):
            saved.append(1)

    request = RequestFactory().get('/missing-page')
    request.session = FakeSession()
    middleware = SessionMiddleware(lambda req: HttpResponse(status=404))
    middleware.process_response(request, HttpResponse(status=404))
    assert saved == []
