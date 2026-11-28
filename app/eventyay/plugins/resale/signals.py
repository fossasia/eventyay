from __future__ import annotations

import logging

from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.signals import order_paid
from eventyay.base.services.orders import OrderError, _cancel_order
from eventyay.control.signals import nav_event
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.signals import front_page_after_content, order_info

from .models import ResaleListing
from .services import (
    ResaleError,
    complete_resale,
    is_position_eligible,
    release_expired_reservations,
    seller_listings_for_order,
)
from .settings import marketplace_is_open

logger = logging.getLogger(__name__)


@receiver(nav_event, dispatch_uid='resale_nav')
def control_nav_resale(sender, request=None, **kwargs):
    if not request or 'eventyay.plugins.resale' not in request.event.get_plugins():
        return []
    url = resolve(request.path_info)
    can_settings = request.user.has_event_permission(
        request.organizer, request.event, 'can_change_event_settings', request
    )
    can_orders = request.user.has_event_permission(
        request.organizer, request.event, 'can_view_orders', request
    )
    if not (can_settings or can_orders):
        return []
    return [
        {
            'label': _('Ticket resale'),
            'url': reverse(
                'plugins:resale:overview',
                kwargs={
                    'event': request.event.slug,
                    'organizer': request.event.organizer.slug,
                },
            ),
            'active': url.namespace == 'plugins:resale',
            'icon': 'exchange',
        }
    ]


@receiver(order_info, dispatch_uid='resale_order_info')
def presale_order_info(sender, request=None, order=None, **kwargs):
    # Show while the feature is enabled so sellers can still see listing status
    # when the marketplace is temporarily closed or suspended.
    if not request or not order:
        return ''
    if not sender.settings.get('resale_enabled', as_type=bool):
        return ''
    if 'eventyay.plugins.resale' not in sender.get_plugins():
        return ''
    market_open = marketplace_is_open(sender)
    with scope(organizer=sender.organizer, event=sender):
        release_expired_reservations(sender)
        rows = []
        for position in order.positions.select_related('product', 'variation'):
            listing = getattr(position, 'resale_listing', None)
            active_listing = (
                listing
                if listing and listing.status != ResaleListing.STATUS_WITHDRAWN
                else None
            )
            ok, _reason = is_position_eligible(sender, position) if market_open else (False, '')
            can_sell = bool(market_open and ok and active_listing is None)
            rows.append(
                {
                    'position': position,
                    'listing': active_listing,
                    'eligible': can_sell,
                    'sell_url': reverse(
                        'plugins:resale:sell',
                        kwargs={
                            'organizer': sender.organizer.slug,
                            'event': sender.slug,
                            'order': order.code,
                            'secret': order.secret,
                            'position': position.pk,
                        },
                    )
                    if can_sell
                    else None,
                }
            )
        existing = list(seller_listings_for_order(order))
    template = get_template('pretixplugins/resale/order_info.html')
    return template.render(
        {
            'event': sender,
            'order': order,
            'rows': rows,
            'listings': existing,
            'request': request,
        },
        request=request,
    )


@receiver(front_page_after_content, dispatch_uid='resale_front_page_link')
def marketplace_link(sender, request=None, **kwargs):
    # after_content always renders (unlike front_page_bottom, which is skipped when
    # guest checkout is disabled). Show whenever the feature is enabled.
    if not request:
        return ''
    if 'eventyay.plugins.resale' not in sender.get_plugins():
        return ''
    if not sender.settings.get('resale_enabled', as_type=bool):
        return ''
    url = eventreverse(sender, 'plugins:resale:marketplace', kwargs={})
    title = _('Ticket marketplace')
    if marketplace_is_open(sender):
        help_text = _('Buy tickets listed by other attendees.')
    else:
        help_text = _('The marketplace is currently closed or suspended.')
    return (
        '<aside class="front-page resale-marketplace-promo" '
        'aria-labelledby="resale-marketplace-heading">'
        f'<h3 id="resale-marketplace-heading">{title}</h3>'
        f'<p>{help_text}</p>'
        f'<p><a class="btn btn-primary" href="{url}">{title}</a></p>'
        '</aside>'
    )


def _listing_ids_from_order(order) -> list[tuple[int, object]]:
    """Return [(listing_id, buyer_position), ...] for all resale vouchers on the order."""
    found = []
    seen = set()
    meta = order.meta_info_data or {}
    meta_id = meta.get('resale_listing_id')
    for position in order.positions.filter(canceled=False).select_related('voucher').order_by('positionid'):
        listing_id = None
        if position.voucher and (position.voucher.tag or '').startswith('resale:'):
            try:
                listing_id = int(position.voucher.tag.split(':', 1)[1])
            except (TypeError, ValueError, IndexError):
                listing_id = None
        if listing_id is None and meta_id and not seen:
            try:
                listing_id = int(meta_id)
            except (TypeError, ValueError):
                listing_id = None
        if listing_id is None or listing_id in seen:
            continue
        seen.add(listing_id)
        found.append((listing_id, position))
    return found


@receiver(order_paid, dispatch_uid='resale_order_paid')
def complete_resale_on_payment(sender, order=None, **kwargs):
    if not order:
        return
    pairs = _listing_ids_from_order(order)
    if not pairs:
        return

    for listing_id, buyer_position in pairs:
        try:
            listing = ResaleListing.objects.select_related('position').get(pk=listing_id, event=sender)
        except ResaleListing.DoesNotExist:
            continue
        try:
            complete_resale(listing=listing, buyer_order=order, buyer_position=buyer_position)
        except ResaleError as exc:
            logger.warning(
                'Resale completion rejected for listing %s on order %s: %s',
                listing_id,
                order.code,
                exc,
            )
            # Late/invalid payment for this listing: cancel this buyer order so they
            # are not left with a ticket that never owned the reservation.
            if listing.status == ResaleListing.STATUS_SOLD and listing.buyer_order_id != order.pk:
                try:
                    _cancel_order(order, send_mail=True, cancel_invoice=True)
                except OrderError:
                    logger.exception(
                        'Failed to cancel late buyer order %s after listing %s already sold',
                        order.code,
                        listing_id,
                    )
        except (OrderError, Exception):
            logger.exception(
                'Failed to complete resale for listing %s on order %s', listing_id, order.code
            )
