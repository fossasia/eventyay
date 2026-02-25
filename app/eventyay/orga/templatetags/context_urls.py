from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def get_dashboard_url(context):
    request = context['request']
    if getattr(request, 'event', None):
        return reverse(
            'eventyay_common:event.index',
            kwargs={
                'organizer': request.event.organizer.slug,
                'event': request.event.slug,
            },
        )
    elif getattr(request, 'organizer', None):
        return request.organizer.orga_urls.base
    return reverse('orga:event.list')
