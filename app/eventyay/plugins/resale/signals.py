from __future__ import annotations

from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.signals import order_paid
from eventyay.control.signals import nav_event
from eventyay.presale.signals import front_page_bottom, order_info

from .models import ResaleListing
from .services import (
    complete_resale,
    is_position_eligible,
    release_expired_reservations,
    seller_listings_for_order,
)
from .settings import marketplace_is_open


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
    if not request or not order or not marketplace_is_open(sender):
        return ''
    with scope(organizer=sender.organizer, event=sender):
        release_expired_reservations(sender)
        rows = []
        for position in order.positions.select_related('product', 'variation'):
            listing = getattr(position, 'resale_listing', None)
            ok, _reason = is_position_eligible(sender, position)
            rows.append(
                {
                    'position': position,
                    'listing': listing if listing and listing.status != ResaleListing.STATUS_WITHDRAWN else None,
                    'eligible': ok and listing is None,
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
                    if ok
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


@receiver(front_page_bottom, dispatch_uid='resale_front_page_link')
def marketplace_link(sender, request=None, **kwargs):
    if not request or not marketplace_is_open(sender):
        return ''
    url = reverse(
        'plugins:resale:marketplace',
        kwargs={'organizer': sender.organizer.slug, 'event': sender.slug},
    )
    return (
        f'<p class="resale-marketplace-link">'
        f'<a class="btn btn-default" href="{url}">'
        f'{_("Ticket marketplace")}'
        f'</a></p>'
    )


@receiver(order_paid, dispatch_uid='resale_order_paid')
def complete_resale_on_payment(sender, order=None, **kwargs):
    if not order:
        return
    listing_id = None
    # Prefer meta stored on the order during checkout.
    meta = order.meta_info_data or {}
    listing_id = meta.get('resale_listing_id')
    if not listing_id:
        # Fall back to voucher tag on a position.
        for position in order.positions.select_related('voucher'):
            if position.voucher and (position.voucher.tag or '').startswith('resale:'):
                try:
                    listing_id = int(position.voucher.tag.split(':', 1)[1])
                except (TypeError, ValueError, IndexError):
                    continue
                break
    if not listing_id:
        return
    try:
        listing = ResaleListing.objects.select_related('position').get(pk=listing_id, event=sender)
    except ResaleListing.DoesNotExist:
        return
    buyer_position = order.positions.filter(canceled=False).order_by('positionid').first()
    if not buyer_position:
        return
    try:
        complete_resale(listing=listing, buyer_order=order, buyer_position=buyer_position)
    except Exception:
        # Logged inside complete_resale; avoid breaking payment confirmation.
        pass
