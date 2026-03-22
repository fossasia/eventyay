from django.http import HttpResponse
from django.test import RequestFactory
from django.test.utils import override_settings

from csp.constants import HEADER, HEADER_REPORT_ONLY
from csp.contrib.rate_limiting import RateLimitedCSPMiddleware
from csp.tests.utils import response

mw = RateLimitedCSPMiddleware(response())
rf = RequestFactory()


@override_settings(CONTENT_SECURITY_POLICY={"REPORT_PERCENTAGE": 10, "DIRECTIVES": {"report-uri": "x"}})
def test_report_percentage() -> None:
    times_seen = 0
    for _ in range(5000):
        request = rf.get("/")
        response = HttpResponse()
        mw.process_response(request, response)
        if "report-uri" in response[HEADER]:
            times_seen += 1
        if "report-to" in response[HEADER]:
            times_seen += 1
    # Roughly 10%
    assert 400 <= times_seen <= 600


@override_settings(CONTENT_SECURITY_POLICY={"REPORT_PERCENTAGE": 9.9, "DIRECTIVES": {"report-uri": "x"}})
def test_report_percentage_float() -> None:
    times_seen = 0
    for _ in range(5000):
        request = rf.get("/")
        response = HttpResponse()
        mw.process_response(request, response)
        if "report-uri" in response[HEADER]:
            times_seen += 1
        if "report-to" in response[HEADER]:
            times_seen += 1
    # Roughly 10%
    assert 400 <= times_seen <= 600


@override_settings(CONTENT_SECURITY_POLICY={"REPORT_PERCENTAGE": 100, "DIRECTIVES": {"report-uri": "x"}})
def test_report_percentage_100() -> None:
    times_seen = 0
    for _ in range(1000):
        request = rf.get("/")
        response = HttpResponse()
        mw.process_response(request, response)
        if "report-uri" in response[HEADER]:
            times_seen += 1
        if "report-to" in response[HEADER]:
            times_seen += 1
    assert times_seen == 1000


@override_settings(CONTENT_SECURITY_POLICY_REPORT_ONLY={"REPORT_PERCENTAGE": 10, "DIRECTIVES": {"report-uri": "x"}})
def test_report_percentage_report_only() -> None:
    times_seen = 0
    for _ in range(5000):
        request = rf.get("/")
        response = HttpResponse()
        mw.process_response(request, response)
        if "report-uri" in response[HEADER_REPORT_ONLY]:
            times_seen += 1
    # Roughly 10%
    assert 400 <= times_seen <= 600


@override_settings(CONTENT_SECURITY_POLICY=None)
def test_no_csp() -> None:
    request = rf.get("/")
    response = HttpResponse()
    mw.process_response(request, response)
    assert HEADER not in response


@override_settings(CONTENT_SECURITY_POLICY_REPORT_ONLY=None)
def test_no_csp_ro() -> None:
    request = rf.get("/")
    response = HttpResponse()
    mw.process_response(request, response)
    assert HEADER_REPORT_ONLY not in response
