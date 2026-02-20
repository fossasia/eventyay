import logging

from django import template
from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict
from django.urls import reverse
from django_scopes import scopes_disabled

from eventyay.base.models import User


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
def short_user_label(user: User | AnonymousUser | None) -> str:
    """
    Compact user display: prefer first name, then full name, then email local part.
    Truncate to 11 chars with ellipsis when longer.
    """
    if not user or not user.is_authenticated:
        return ''
    # Try using first part of full name
    name_parts = user.fullname.split() if user.fullname else []
    label = name_parts[0] if name_parts else ''
    if not label:
        # Fall back to first part of primary email
        label = user.primary_email.split('@')[0]
    # Truncate to 11 chars with ellipsis
    return (label[:11] + '…') if len(label) > 11 else label


@register.filter
def startswith(value, arg):
    """Usage: {% if value|startswith:"arg" %}"""
    if isinstance(value, str):
        return value.startswith(arg)
    return False


@register.simple_tag(takes_context=True)
def tickets_tab_visible(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    if request and not event.user_can_view_tickets(getattr(request, 'user', None), request=request):
        return False
    productnum = context.get('productnum')
    if productnum is not None:
        try:
            return int(productnum) != 0
        except (TypeError, ValueError):
            return bool(productnum)
    channel = getattr(getattr(request, 'sales_channel', None), 'identifier', 'web')
    with scopes_disabled():
        return event.products.filter_available(channel=channel).exists()


@register.simple_tag(takes_context=True)
def can_view_tickets(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.user_can_view_tickets(getattr(request, 'user', None), request=request)


@register.simple_tag(takes_context=True)
def can_view_talks(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.user_can_view_talks(getattr(request, 'user', None), request=request)


@register.simple_tag(takes_context=True)
def private_testmode_tickets_enabled(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.private_testmode and event.settings.get('private_testmode_tickets', True, as_type=bool)


@register.simple_tag(takes_context=True)
def private_testmode_talks_enabled(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    if not event:
        return False
    return event.private_testmode and event.settings.get('private_testmode_talks', False, as_type=bool)


@register.simple_tag(takes_context=True)
def is_event_team_member(context, event=None):
    request = context.get('request')
    event = event or getattr(request, 'event', None)
    user = getattr(request, 'user', None)
    if not event or not user or user.is_anonymous:
        return False
    return user.has_event_permission(event.organizer, event, request=request)
