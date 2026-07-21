import logging
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


def build_login_url_with_next(next_path):
    """Build ``/common/login/?next=…`` for post-login return navigation."""
    return f'{reverse("eventyay_common:auth.login")}?{urlencode({"next": next_path})}'


def login_redirect_with_next(request, next_path=None):
    """
    Send anonymous users to login, then back to ``next_path`` (defaults to the
    current request path). AJAX callers receive JSON with ``login_url``.
    """
    login_url = build_login_url_with_next(next_path or request.get_full_path())
    if is_ajax_request(request):
        return JsonResponse({'login_url': login_url}, status=HTTPStatus.UNAUTHORIZED)
    return redirect(login_url)


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
