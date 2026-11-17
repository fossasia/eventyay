import unicodedata
from urllib.parse import urlencode, urlsplit

from django.core import signing
from django.http import HttpRequest
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


RETURN_ORIGIN_MAX_AGE = 24 * 60 * 60


def get_redirect_target(request: HttpRequest) -> str | None:
    """Read a submitted destination before falling back to query parameters."""
    return (
        request.POST.get('next')
        or request.POST.get('redirect_url')
        or request.GET.get('next')
        or request.GET.get('redirect_url')
    )


def is_internal_url(request: HttpRequest, target: str) -> bool:
    """Check the destination against the current request's host and scheme."""
    return url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )


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


def external_link_origin(request: HttpRequest | None) -> str:
    """Attest the source origin so Cancel can return across custom-domain handoffs."""
    if not request:
        return ''
    return signing.dumps(request.build_absolute_uri('/'), salt='external-link-return-origin')


def safe_return_url(request: HttpRequest, target: str | None, origin_signature: str | None = None) -> str:
    """Allow cancellation within this site or an origin attested by a rendered page."""
    fallback = reverse('presale:index')
    destination = validate_redirect_url(request, target or '')
    if not destination:
        return fallback
    target_parts = urlsplit(destination)
    if request.is_secure() and target_parts.scheme == 'http':
        return fallback
    if target_parts.path.rstrip('/') in {
        reverse('eventyay_common:external-link').rstrip('/'),
        reverse('redirect').rstrip('/'),
    }:
        return fallback
    if is_internal_url(request, destination):
        return destination
    try:
        origin = signing.loads(
            origin_signature or '', salt='external-link-return-origin', max_age=RETURN_ORIGIN_MAX_AGE
        )
    except signing.BadSignature:
        return fallback
    if not isinstance(origin, str) or not validate_redirect_url(request, origin):
        return fallback
    source = urlsplit(origin)
    source_port = source.port or (443 if source.scheme == 'https' else 80)
    target_port = target_parts.port or (443 if target_parts.scheme == 'https' else 80)
    if (source.scheme, source.hostname, source_port) == (
        target_parts.scheme,
        target_parts.hostname,
        target_port,
    ):
        return destination
    return fallback


def safe_redirect_url(
    request: HttpRequest, target: str | None, *, return_url: str | None = None, return_origin: str | None = None
) -> str:
    """Send valid external destinations through the confirmation page."""
    destination = validate_redirect_url(request, target or '')
    if not destination:
        return reverse('eventyay_common:dashboard')
    if is_internal_url(request, destination):
        return destination
    cancel = reverse('eventyay_common:dashboard') if return_url is None else return_url
    params = {'next': destination, 'return_url': safe_return_url(request, cancel, return_origin)}
    if return_origin:
        params['return_origin'] = return_origin
    return reverse('eventyay_common:external-link') + '?' + urlencode(params)


def safelink(url: str, *, return_url: str | None = None, return_origin: str | None = None) -> str:
    """Wrap a destination in a signed redirect link."""
    signer = signing.Signer(salt='safe-redirect')
    params = {'url': signer.sign(url)}
    if return_url is not None:
        params['return_url'] = return_url
    if return_origin:
        params['return_origin'] = return_origin
    return reverse('redirect') + '?' + urlencode(params)
