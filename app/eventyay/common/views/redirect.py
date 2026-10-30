import urllib.parse

from django.core import signing
from django.http import HttpRequest, HttpResponse
from django.urls import reverse

from eventyay.base.views.redirect import redir_view


def redirect_view(request: HttpRequest) -> HttpResponse:
    return redir_view(request)


def safelink(url: str) -> str:
    """Wrap a URL with our redirect view to check if the user is about to go to external site."""
    signer = signing.Signer(salt='safe-redirect')
    return reverse('redirect') + '?url=' + urllib.parse.quote(signer.sign(url))
