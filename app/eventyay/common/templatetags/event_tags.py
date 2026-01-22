import logging

from django import template
from django.contrib.auth.models import AnonymousUser
from django.http import QueryDict
from django.urls import reverse

from eventyay.base.models import Order, OrderPosition, User


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
def short_user_label(user: User | AnonymousUser) -> str:
    """
    Compact user display: prefer first name, then name, then email local part.
    Truncate to 11 chars with ellipsis when longer.
    """
    if not user.is_authenticated:
        return ''
    # Try using first part of full name
    label = user.fullname.split()[0] if user.fullname else ''
    if not label:
        # Fall back to first part of primary email
        label = user.primary_email.split('@')[0]
    # Truncate to 11 chars with ellipsis
    return (label[:11] + '…') if len(label) > 11 else label


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

    user = request.user
    if not user.primary_email:
        return False

    allowed_statuses = [Order.STATUS_PAID]
    if event.settings.venueless_allow_pending:
        allowed_statuses.append(Order.STATUS_PENDING)

    if event.settings.venueless_all_products:
        return OrderPosition.objects.filter(
            order__event=event,
            order__email__iexact=user.primary_email,
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
        order__email__iexact=user.primary_email,
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
