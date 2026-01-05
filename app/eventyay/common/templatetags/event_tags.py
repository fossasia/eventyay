import logging

from django import template
from django.http import QueryDict
from django.urls import reverse

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter
def get_feature_flag(event, feature_flag: str):
    return event.get_feature_flag(feature_flag)


@register.simple_tag(takes_context=True)
def cfp_locale_switch_url(context, locale_code):
    request = context.get('request')
    event = getattr(request, 'event', None)
    if not request or not event:
        logger.warning("cfp_locale_switch_url called without request.event")
        return ''
    if not event.organizer:
        logger.warning(
            "cfp_locale_switch_url called with event %s missing organizer",
            getattr(event, 'slug', '<unknown>'),
        )
        return ''
    base = reverse(
        'cfp:locale.set',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    query = QueryDict(mutable=True)
    query['locale'] = locale_code
    query['next'] = request.get_full_path()
    return f"{base}?{query.urlencode()}"


@register.filter
def short_user_label(user):
    """
    Compact user display: prefer first name, then name, then email local part.
    Truncate to 11 chars with ellipsis when longer.
    """
    if not user:
        return ''
    first = getattr(user, 'first_name', None) or getattr(user, 'firstname', None)
    if not first:
        fullname = getattr(user, 'fullname', None) or getattr(user, 'name', None)
        if fullname:
            parts = fullname.split()
            first = parts[0] if parts else fullname
    email = getattr(user, 'email', '') or ''
    label = (first or '').strip() or (email.split('@')[0] if email else '')
    if len(label) > 11:
        label = label[:11] + '…'
    return label

