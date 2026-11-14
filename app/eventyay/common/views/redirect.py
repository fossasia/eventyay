from django.http import HttpRequest, HttpResponse

from eventyay.base.views.redirect import redir_view
from eventyay.common.redirects import safelink as safelink


def redirect_view(request: HttpRequest) -> HttpResponse:
    return redir_view(request)
