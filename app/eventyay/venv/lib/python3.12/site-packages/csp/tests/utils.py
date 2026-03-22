from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from django.http import HttpResponse
from django.template import Context, Template, engines
from django.test import RequestFactory
from django.utils.functional import SimpleLazyObject

from csp.middleware import CSPMiddleware

if TYPE_CHECKING:
    from django.http import HttpRequest


def response(*args: Any, headers: dict[str, str] | None = None, **kwargs: Any) -> Callable[[HttpRequest], HttpResponse]:
    def get_response(req: HttpRequest) -> HttpResponse:
        response = HttpResponse(*args, **kwargs)
        if headers:
            for k, v in headers.items():
                response.headers[k] = v
        return response

    return get_response


JINJA_ENV = engines["jinja2"]
mw = CSPMiddleware(response())
rf = RequestFactory()


class ScriptTestBase(ABC):
    def assert_template_eq(self, tpl1: str, tpl2: str) -> None:
        aaa = tpl1.replace("\n", "").replace("  ", "")
        bbb = tpl2.replace("\n", "").replace("  ", "")
        assert aaa == bbb, f"{aaa} != {bbb}"

    def process_templates(self, tpl: str, expected: str) -> tuple[str, str]:
        request = rf.get("/")
        mw.process_request(request)
        nonce = getattr(request, "csp_nonce")
        assert isinstance(nonce, SimpleLazyObject)
        return (self.render(tpl, request).strip(), expected.format(nonce))

    @abstractmethod
    def render(self, template_string: str, request: HttpRequest) -> str: ...


class ScriptTagTestBase(ScriptTestBase):
    def render(self, template_string: str, request: HttpRequest) -> str:
        context = Context({"request": request})
        template = Template(template_string)
        return template.render(context)


class ScriptExtensionTestBase(ScriptTestBase):
    def render(self, template_string: str, request: HttpRequest) -> str:
        context = {"request": request}
        template = JINJA_ENV.from_string(template_string)
        return template.render(context)
