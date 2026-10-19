import unicodedata
from urllib.parse import urlencode, urlsplit

from django.http import HttpRequest
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def validate_redirect_url(request: HttpRequest, target: str) -> str:
    """Accept local URLs and unambiguous HTTP(S) destinations only."""
    if not target or '\\' in target or any(unicodedata.category(char).startswith('C') for char in target):
        return ''
    target = target.strip()
    try:
        parts = urlsplit(target)
        if parts.username is not None or parts.password is not None:
            return ''
        if parts.netloc and (not parts.hostname or parts.port == 0):
            return ''
    except ValueError:
        return ''
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={parts.netloc}):
        return ''
    if parts.netloc:
        return f'{request.scheme}:{target}' if not parts.scheme else target
    return target if target.startswith('/') else ''


def safe_redirect_url(request: HttpRequest, target: str | None) -> str:
    """Send valid external destinations through the confirmation page."""
    destination = validate_redirect_url(request, target or '')
    if not destination:
        return reverse('eventyay_common:dashboard')
    if url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}):
        return destination
    return reverse('eventyay_common:external-link') + '?' + urlencode({'next': destination})
