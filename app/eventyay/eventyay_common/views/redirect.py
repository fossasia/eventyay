from urllib.parse import urlsplit

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from eventyay.common.redirects import is_internal_url, safe_return_url, validate_redirect_url


@never_cache
@require_safe
def external_link(request: HttpRequest) -> HttpResponse:
    destination = validate_redirect_url(request, request.GET.get('next') or request.GET.get('redirect_url', ''))
    if not destination:
        return HttpResponseBadRequest('Invalid destination')
    if is_internal_url(request, destination):
        if urlsplit(destination).path.rstrip('/') == request.path.rstrip('/'):
            return HttpResponseRedirect(reverse('eventyay_common:dashboard'))
        return HttpResponseRedirect(destination)
    return_url = safe_return_url(request, request.GET.get('return_url'), request.GET.get('return_origin'))
    response = render(
        request, 'eventyay_common/external_link.html', {'destination': destination, 'return_url': return_url}
    )
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
