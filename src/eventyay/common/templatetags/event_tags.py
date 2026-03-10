import logging

from django import template
from django.http import QueryDict
from django.urls import reverse

from django_scopes import scopes_disabled

from eventyay.base.models import Order, OrderPosition

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
    Compact user display: prefer first name, then full name, then email local part.
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


@register.simple_tag(takes_context=True)
def user_has_valid_ticket(context, event=None):
    """Return True if the current authenticated user has a valid order/ticket granting video access.

    Mirrors the access rules used by the presale online video join flow.
    """
    request = context.get('request')
    if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
        return False

    event = event or getattr(request, 'event', None)
    if not event:
        return False

    if not request.user.email:
        return False

    allowed_statuses = [Order.STATUS_PAID]
    if event.settings.venueless_allow_pending:
        allowed_statuses.append(Order.STATUS_PENDING)

    if event.settings.venueless_all_products:
        return OrderPosition.objects.filter(
            order__event=event,
            order__email__iexact=request.user.email,
            order__status__in=allowed_statuses,
            product__admission=True,
            canceled=False,
            addon_to__isnull=True,
        ).exists()

    allowed_products = event.settings.venueless_products or []
    if not allowed_products:
        return False

    return OrderPosition.objects.filter(
        order__event=event,
        order__email__iexact=request.user.email,
        order__status__in=allowed_statuses,
        product_id__in=allowed_products,
        canceled=False,
        addon_to__isnull=True,
    ).exists()


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
