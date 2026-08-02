from django.http import Http404, HttpResponse
from django.test import RequestFactory

from eventyay.base.views.errors import page_not_found
from eventyay.common.middleware.domains import SessionMiddleware as CommonSessionMiddleware
from eventyay.multidomain.middlewares import SessionMiddleware as MultidomainSessionMiddleware


def test_page_not_found_returns_static_response():
    rf = RequestFactory()
    request = rf.get('/some-invalid-path-12345')
    response = page_not_found(request, Http404('Not found'))

    assert response.status_code == 404
    assert response.content == b'<html><body><h1>404 Not Found</h1></body></html>'
    assert response.headers['content-type'] == 'text/html'
    assert getattr(response, 'xframe_options_exempt', False) is True


def test_session_middleware_skips_save_on_404_when_unmodified():
    rf = RequestFactory()
    request = rf.get('/some-invalid-path-12345')

    class DummySession(dict):
        accessed = True
        modified = False
        saved = False
        session_key = 'testkey'

        def is_empty(self):
            return True

        def save(self):
            self.saved = True

    request.session = DummySession()
    response = HttpResponse(status=404)

    middleware = MultidomainSessionMiddleware(lambda req: response)
    middleware.process_response(request, response)
    assert request.session.saved is False

    common_middleware = CommonSessionMiddleware(lambda req: response)
    common_middleware.process_response(request, response)
    assert request.session.saved is False


def test_session_middleware_saves_on_404_when_modified():
    rf = RequestFactory()
    request = rf.get('/some-invalid-path-12345')
    request.host = 'example.com'

    class DummySession(dict):
        accessed = True
        modified = True
        saved = False
        session_key = 'testkey'

        def is_empty(self):
            return False

        def get_expire_at_browser_close(self):
            return True

        def save(self):
            self.saved = True

    request.session = DummySession()
    response = HttpResponse(status=404)

    middleware = MultidomainSessionMiddleware(lambda req: response)
    middleware.process_response(request, response)
    assert request.session.saved is True
