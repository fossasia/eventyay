import urllib.parse

from django.core import signing
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.urls import reverse

from eventyay.common.redirects import safe_redirect_url


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


def safelink(url, *, return_url: str | None = None, return_origin: str | None = None):
    signer = signing.Signer(salt='safe-redirect')
    target = reverse('redirect') + '?url=' + urllib.parse.quote(signer.sign(url))
    params = {}
    if return_url is not None:
        params['return_url'] = return_url
    if return_origin:
        params['return_origin'] = return_origin
    return target + ('&' + urllib.parse.urlencode(params) if params else '')
