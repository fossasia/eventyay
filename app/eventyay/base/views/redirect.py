from django.core import signing
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse

from eventyay.common.redirects import safe_redirect_url
from eventyay.common.redirects import safelink as safelink


def redir_view(request):
    signer = signing.Signer(salt='safe-redirect')
    try:
        url = signer.unsign(request.GET.get('url', ''))
    except signing.BadSignature:
        return HttpResponseBadRequest('Invalid parameter')
    r = HttpResponseRedirect(
        safe_redirect_url(
            request,
            url,
            return_url=request.GET.get('return_url') or reverse('presale:index'),
            return_origin=request.GET.get('return_origin'),
        )
    )
    r['X-Robots-Tag'] = 'noindex'
    return r
