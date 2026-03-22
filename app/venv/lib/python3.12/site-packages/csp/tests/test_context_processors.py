from django.http import HttpResponse
from django.test import RequestFactory

import pytest

from csp.context_processors import nonce
from csp.exceptions import CSPNonceError
from csp.middleware import CSPMiddleware
from csp.tests.utils import response

rf = RequestFactory()
mw = CSPMiddleware(response())


def test_nonce_context_processor() -> None:
    request = rf.get("/")
    mw.process_request(request)
    context = nonce(request)

    response = HttpResponse()
    csp_nonce = getattr(request, "csp_nonce")
    mw.process_response(request, response)

    assert context["CSP_NONCE"] == csp_nonce


def test_nonce_context_processor_after_response() -> None:
    request = rf.get("/")
    mw.process_request(request)
    context = nonce(request)

    response = HttpResponse()
    csp_nonce = getattr(request, "csp_nonce")
    mw.process_response(request, response)

    assert context["CSP_NONCE"] == csp_nonce

    with pytest.raises(CSPNonceError):
        str(getattr(request, "csp_nonce"))


def test_nonce_context_processor_with_middleware_disabled() -> None:
    request = rf.get("/")
    context = nonce(request)

    assert context["CSP_NONCE"] == ""
