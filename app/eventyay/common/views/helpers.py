import logging
from functools import wraps
from http import HTTPStatus
from urllib.parse import urlencode

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)


def is_form_bound(request, form_name, form_param='form'):
    return request.method == 'POST' and request.POST.get(form_param) == form_name


def is_ajax_request(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )


def is_widget_iframe_request(request, trust_session=False):
    """
    True if the request is rendered inside the widget iframe (``?iframe=1`` or widget namespace).
    ``iframe_session`` is only honoured when ``trust_session`` is set, e.g. for
    namespaced widget carts, so a prior visit cannot alter unframed pages.
    """
    if 'iframe' in request.GET:
        return True
    if getattr(request, 'resolver_match', None) and request.resolver_match.kwargs.get('cart_namespace'):
        return True
    return bool(trust_session and request.session.get('iframe_session'))


def allow_frame_if_iframe_param(view_func):
    """
    Drop ``X-Frame-Options`` when the request is explicitly marked as frame-safe
    via ``?iframe=1``. Used for auth pages (forgot password, signup) that need to
    render inside the widget checkout popup without opening a new tab.
    """

    def wrapped_view(request, *args, **kwargs):
        resp = view_func(request, *args, **kwargs)
        if 'iframe' in request.GET or 'iframe=1' in request.GET.get('next', '') or is_widget_iframe_request(request):
            resp.xframe_options_exempt = True
        return resp

    return wraps(view_func)(wrapped_view)


def build_login_url_with_next(next_path):
    """Build ``/login/?next=…`` for post-login return navigation."""
    params = {'next': next_path}
    if 'iframe=1' in next_path or 'iframe' in next_path:
        params['iframe'] = '1'
    return f'{reverse("auth.login")}?{urlencode(params)}'


def login_redirect_with_next(request, next_path=None):
    """
    Send anonymous users to login, then back to ``next_path`` (defaults to the
    current request path). AJAX callers receive JSON with ``login_url``.
    """
    next_url = next_path or request.get_full_path()
    login_url = build_login_url_with_next(next_url)
    if is_ajax_request(request):
        return JsonResponse({'login_url': login_url}, status=HTTPStatus.UNAUTHORIZED)
    resp = redirect(login_url)
    if is_widget_iframe_request(request) or 'iframe=1' in login_url:
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
