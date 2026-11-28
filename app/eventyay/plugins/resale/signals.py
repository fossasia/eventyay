from __future__ import annotations

import logging

from django.db.models import Q
from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.signals import order_paid
from eventyay.base.services.orders import OrderChangeManager, OrderError, _cancel_order
from eventyay.control.signals import nav_event, order_info as control_order_info
from eventyay.multidomain.urlreverse import eventreverse
from eventyay.presale.signals import front_page_after_content, order_info

from .models import ResaleListing
from .services import (
    RESALE_ROLE_BUYER,
    RESALE_ROLE_SELLER,
    ResaleError,
    complete_resale,
    is_position_eligible,
    order_resale_meta,
    release_expired_reservations,
    seller_listings_for_order,
    tag_order_resale,
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
            ok, _reason = is_position_eligible(sender, position) if market_open else (False, '')
            # Withdrawn listings stay visible for status monitoring and can be relisted.
            blocking = listing is not None and listing.status in (
                ResaleListing.STATUS_AVAILABLE,
                ResaleListing.STATUS_RESERVED,
                ResaleListing.STATUS_SOLD,
            )
            can_sell = bool(market_open and ok and not blocking)
            rows.append(
                {
                    'position': position,
                    'listing': listing,
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


@receiver(control_order_info, dispatch_uid='resale_control_order_info')
def resale_control_order_info(sender, request=None, order=None, **kwargs):
    """Show a RESOLD / resale-purchase panel on the organizer order page."""
    if not request or not order:
        return ''
    if 'eventyay.plugins.resale' not in sender.get_plugins():
        return ''

    meta = order_resale_meta(order)
    with scope(organizer=sender.organizer, event=sender):
        listing = None
        listing_id = meta.get('resale_listing_id')
        if listing_id:
            listing = (
                ResaleListing.objects.filter(pk=listing_id, event=sender)
                .select_related('seller_order', 'buyer_order')
                .first()
            )
        if listing is None:
            listing = (
                ResaleListing.objects.filter(event=sender, status=ResaleListing.STATUS_SOLD)
                .filter(Q(seller_order=order) | Q(buyer_order=order))
                .select_related('seller_order', 'buyer_order')
                .order_by('-sold_at', '-pk')
                .first()
            )
        if listing is None and not meta:
            return ''

        role = meta.get('resale_role')
        if not role and listing:
            if listing.seller_order_id == order.pk:
                role = RESALE_ROLE_SELLER
            elif listing.buyer_order_id == order.pk:
                role = RESALE_ROLE_BUYER
        if role not in (RESALE_ROLE_SELLER, RESALE_ROLE_BUYER):
            return ''

        related_code = meta.get('resale_related_order')
        if not related_code and listing:
            if role == RESALE_ROLE_SELLER and listing.buyer_order_id:
                related_code = listing.buyer_order.code
            elif role == RESALE_ROLE_BUYER and listing.seller_order_id:
                related_code = listing.seller_order.code

        # Backfill durable tags for sales completed before tagging existed.
        if listing and not meta.get('resale_role'):
            if listing.seller_order_id:
                tag_order_resale(
                    listing.seller_order,
                    role=RESALE_ROLE_SELLER,
                    listing=listing,
                    related_order=listing.buyer_order,
                )
            if listing.buyer_order_id:
                tag_order_resale(
                    listing.buyer_order,
                    role=RESALE_ROLE_BUYER,
                    listing=listing,
                    related_order=listing.seller_order,
                )

    template = get_template('pretixplugins/resale/control_order_info.html')
    return template.render(
        {
            'event': sender,
            'order': order,
            'request': request,
            'role': role,
            'listing': listing,
            'related_code': related_code,
            'is_seller': role == RESALE_ROLE_SELLER,
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


def _invalidate_rejected_buyer_position(order, buyer_position, listing_id: int) -> None:
    """Cancel only the rejected resale position, or the whole order if it was the last one.

    Avoids wiping other successfully completed resale positions on the same order.
    """
    remaining = order.positions.filter(canceled=False).exclude(pk=buyer_position.pk).count()
    try:
        if remaining == 0:
            _cancel_order(order, send_mail=True, cancel_invoice=True)
        else:
            ocm = OrderChangeManager(order, notify=True)
            ocm.cancel(buyer_position)
            ocm.commit(check_quotas=False)
    except OrderError:
        logger.exception(
            'Failed to invalidate rejected resale position %s on order %s (listing %s)',
            buyer_position.pk,
            order.code,
            listing_id,
        )


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
            listing.refresh_from_db()
            # Any rejection (sold to someone else, expired reservation, lost hold) must
            # not leave this buyer with a paid ticket for a listing they do not own.
            owns_sale = (
                listing.status == ResaleListing.STATUS_SOLD and listing.buyer_order_id == order.pk
            )
            if not owns_sale:
                _invalidate_rejected_buyer_position(order, buyer_position, listing_id)
        except OrderError:
            logger.exception(
                'Failed to complete resale for listing %s on order %s', listing_id, order.code
            )
        except Exception:
            logger.exception(
                'Unexpected error completing resale for listing %s on order %s',
                listing_id,
                order.code,
            )
