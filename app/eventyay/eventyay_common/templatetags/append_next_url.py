from urllib.parse import urlencode

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def append_next(context, next_url=None):
    request = context.get('request')
    params = {}
    if next_url and str(next_url).strip():
        params['next'] = next_url
    if request and 'iframe' in request.GET:
        params['iframe'] = '1'
    if params:
        return f'?{urlencode(params)}'
    return ''
