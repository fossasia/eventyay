from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from eventyay.common.redirects import validate_redirect_url


@never_cache
@require_safe
def external_link(request: HttpRequest) -> HttpResponse:
    destination = validate_redirect_url(request, request.GET.get('next') or request.GET.get('redirect_url', ''))
    if not destination:
        return HttpResponseBadRequest('Invalid destination')
    if url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}):
        return HttpResponseRedirect(destination)
    response = render(request, 'eventyay_common/external_link.html', {'destination': destination})
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
