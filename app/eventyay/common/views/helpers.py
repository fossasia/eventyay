import logging
from functools import wraps
from http import HTTPStatus
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

logger = logging.getLogger(__name__)


def is_form_bound(request, form_name, form_param='form'):
    return request.method == 'POST' and request.POST.get(form_param) == form_name


def is_ajax_request(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def is_safe_redirect_url(url, request=None):
    """
    Validate that an URL is safe to redirect to (preventing open redirect vulnerabilities).
    Allows relative paths and absolute URLs matching the current request's host.
    """
    if not url or not isinstance(url, str):
        return False
    allowed_hosts = {request.get_host()} if request and hasattr(request, 'get_host') else None
    return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts)


def is_namespaced_widget_request(request):
    """
    True ONLY if the request is on a verified namespaced widget route (has a valid
    16-character alphanumeric cart_namespace).
    Bare query parameters (?iframe=1), unscoped session flags, or headers do NOT grant
    namespaced widget status.
    """
    if not request:
        return False
    resolver_match = getattr(request, 'resolver_match', None)
    if resolver_match and resolver_match.kwargs:
        ns = resolver_match.kwargs.get('cart_namespace')
        if ns and isinstance(ns, str) and len(ns) == 16 and ns.isalnum():
            return True
    return False


def is_trusted_widget_framing_authorized(request, kwargs=None):
    """
    Keep framing enabled ONLY for namespaced widget routes or an explicit allow-listed embedding origin.
    Do NOT use query parameters (?iframe=1), unscoped session flags, or Sec-Fetch-Dest as framing authorization.
    """
    if not request:
        return False
    if is_namespaced_widget_request(request):
        return True
    if kwargs and kwargs.get('cart_namespace'):
        ns = kwargs.get('cart_namespace')
        if isinstance(ns, str) and len(ns) == 16 and ns.isalnum():
            return True
    allowed_origins = getattr(settings, 'EVENTYAY_FRAME_ALLOW_ORIGINS', None)
    if allowed_origins:
        origin = getattr(request, 'headers', {}).get('Origin') or (
            request.META.get('HTTP_ORIGIN') if hasattr(request, 'META') else None
        )
        if origin and origin in allowed_origins:
            return True
    return False


def is_widget_destination_or_origin(url, request=None):
    """
    Check if an URL is a safe internal widget destination (has /widget/ in path or iframe query param).
    Used for return URL context propagation.
    """
    if not is_safe_redirect_url(url, request):
        return False
    try:
        parsed = urlparse(url)
        return (
            '/widget/' in parsed.path
            or '1' in parse_qs(parsed.query).get('iframe', [])
            or 'true' in parse_qs(parsed.query).get('iframe', [])
        )
    except ValueError:
        return False


def is_widget_iframe_request(request, trust_session=False):
    """
    True if the request is rendered inside the widget iframe (``?iframe=1`` or widget namespace).
    NOTE: Strictly for context propagation (UI layout, cookie partitioning, URL query params).
    DO NOT use this for framing authorization (xframe_options_exempt).
    """
    if not request:
        return False
    if request.GET.get('iframe') in ('1', 'true'):
        return True
    if getattr(request, 'resolver_match', None) and request.resolver_match.kwargs.get('cart_namespace'):
        return True
    if getattr(request, 'path_info', '').find('/widget/') != -1:
        return True
    return bool(trust_session and getattr(request, 'session', {}).get('iframe_session'))


def allow_frame_if_iframe_param(view_func):
    """
    Restrict frame exemptions to trusted widget contexts:
    Keep framing enabled ONLY for namespaced widget routes or an explicit allow-listed embedding origin.
    Do NOT use query parameters (?iframe=1), unscoped session flags, or Sec-Fetch-Dest as framing authorization.
    """

    def wrapped_view(request, *args, **kwargs):
        resp = view_func(request, *args, **kwargs)
        if not resp:
            return resp

        if is_trusted_widget_framing_authorized(request, kwargs):
            resp.xframe_options_exempt = True
        return resp

    return wraps(view_func)(wrapped_view)


def build_login_url_with_next(next_path, request=None):
    """Build ``/login/?next=…`` for post-login return navigation."""
    params = {'next': next_path}
    if (
        is_widget_destination_or_origin(next_path, request)
        or (request and is_widget_iframe_request(request))
    ):
        params['iframe'] = '1'

    return f'{reverse("auth.login")}?{urlencode(params)}'


def login_redirect_with_next(request, next_path=None):
    """
    Send anonymous users to login, then back to ``next_path`` (defaults to the
    current request path). AJAX callers receive JSON with ``login_url``.
    """
    next_url = next_path or request.get_full_path()
    login_url = build_login_url_with_next(next_url, request=request)
    if is_ajax_request(request):
        return JsonResponse({'login_url': login_url}, status=HTTPStatus.UNAUTHORIZED)
    resp = redirect(login_url)
    if is_trusted_widget_framing_authorized(request):
        resp.xframe_options_exempt = True
    return resp


def redirect_or_json_redirect(request, redirect_url):
    """Return JSON ``redirect_url`` for AJAX, otherwise an HTTP redirect."""
    if is_ajax_request(request):
        return JsonResponse({'redirect_url': redirect_url}, status=HTTPStatus.OK)
    return redirect(redirect_url)


def get_static(request, path, content_type, organizer=None, event=None, **kwargs):  # pragma: no cover
    path = settings.BASE_DIR / 'static' / path
    if not path.exists():
        logger.warning("Static asset %s not found", path)
        raise Http404()
    logger.debug("Serving static asset %s", path)
    return FileResponse(open(path, 'rb'), content_type=content_type, as_attachment=False)
