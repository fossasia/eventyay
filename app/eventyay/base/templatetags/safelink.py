from django import template

from eventyay.common.redirects import external_link_origin
from eventyay.helpers.safedownload import get_token

from ..views.redirect import safelink as sl


register = template.Library()


@register.simple_tag(takes_context=True)
def safelink(context, url):
    request = context.get('request')
    if request is None:
        return sl(url)
    return sl(url, return_url=request.build_absolute_uri(), return_origin=external_link_origin(request))


@register.simple_tag
def answer_token(request, answer):
    return get_token(request, answer)
