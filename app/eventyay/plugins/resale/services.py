from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.models import Order, OrderPayment, OrderPosition, OrderRefund, Quota
from eventyay.base.services.orders import OrderChangeManager, OrderError

from .models import ResaleListing
from .settings import (
    FEE_MODE_PERCENT,
    eligible_product_ids,
    marketplace_is_open,
    reservation_ttl,
)

logger = logging.getLogger(__name__)


class ResaleError(Exception):
    """Domain error for marketplace operations (safe to show to users)."""


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_fee(event, price: Decimal) -> Decimal:
    mode = event.settings.get('resale_fee_mode', as_type=str) or FEE_MODE_FIXED
    price = quantize_money(price)
    if mode == FEE_MODE_PERCENT:
        percent = Decimal(event.settings.get('resale_fee_percent', as_type=Decimal) or 0)
        fee = quantize_money(price * percent / Decimal('100'))
    else:
        fee = quantize_money(Decimal(event.settings.get('resale_fee_fixed', as_type=Decimal) or 0))
    return min(fee, price)


def calculate_seller_payout(event, price: Decimal) -> tuple[Decimal, Decimal]:
    fee = calculate_fee(event, price)
    return fee, quantize_money(price - fee)


def max_allowed_price(position: OrderPosition) -> Decimal:
    return quantize_money(position.price)


def position_has_checkin(position: OrderPosition) -> bool:
    return position.checkins.exists()


def is_position_eligible(event, position: OrderPosition) -> tuple[bool, str]:
    """Return (ok, reason) for whether a position may be listed."""
    if not marketplace_is_open(event):
        return False, _('The ticket marketplace is not open.')
    if position.canceled:
        return False, _('This ticket has been cancelled.')
    if position.order.status not in (Order.STATUS_PAID, Order.STATUS_PENDING):
        return False, _('Only paid or pending orders can be resold.')
    if position.order.status == Order.STATUS_PENDING and position.order.pending_sum > 0:
        return False, _('This order is not fully paid.')
    if position.order.status != Order.STATUS_PAID:
        # Prefer fully paid seller orders so refunds are straightforward.
        return False, _('Only paid tickets can be listed for resale.')
    product_ids = eligible_product_ids(event)
    if product_ids and position.product_id not in product_ids:
        return False, _('This ticket type is not eligible for resale.')
    if position_has_checkin(position):
        return False, _('Checked-in tickets cannot be resold.')
    if hasattr(position, 'resale_listing'):
        listing = position.resale_listing
        if listing.status in (
            ResaleListing.STATUS_AVAILABLE,
            ResaleListing.STATUS_RESERVED,
            ResaleListing.STATUS_SOLD,
        ):
            return False, _('This ticket is already listed or sold.')
    return True, ''


@transaction.atomic
def create_listing(*, event, position: OrderPosition, price: Decimal) -> ResaleListing:
    with scope(organizer=event.organizer, event=event):
        position = (
            OrderPosition.objects.select_for_update()
            .select_related('order', 'product')
            .get(pk=position.pk, order__event=event)
        )
        ok, reason = is_position_eligible(event, position)
        if not ok:
            raise ResaleError(reason)

        price = quantize_money(price)
        max_price = max_allowed_price(position)
        if price <= Decimal('0.00'):
            raise ResaleError(_('The resale price must be greater than zero.'))
        if price > max_price:
            raise ResaleError(
                _('The resale price cannot exceed the original purchase price of {price}.').format(
                    price=max_price
                )
            )

        fee, payout = calculate_seller_payout(event, price)
        listing = ResaleListing.objects.create(
            event=event,
            position=position,
            seller_order=position.order,
            price=price,
            original_price=max_price,
            fee_amount=fee,
            seller_payout=payout,
            status=ResaleListing.STATUS_AVAILABLE,
        )
        position.order.log_action(
            'eventyay.plugins.resale.listing.created',
            data={
                'listing': listing.pk,
                'position': position.pk,
                'price': str(price),
                'fee': str(fee),
                'payout': str(payout),
            },
        )
        return listing


@transaction.atomic
def withdraw_listing(*, listing: ResaleListing) -> ResaleListing:
    listing = ResaleListing.objects.select_for_update().select_related('seller_order').get(pk=listing.pk)
    if listing.status == ResaleListing.STATUS_RESERVED:
        raise ResaleError(_('This listing is currently reserved and cannot be withdrawn.'))
    if listing.status == ResaleListing.STATUS_SOLD:
        raise ResaleError(_('This listing has already been sold.'))
    if listing.status == ResaleListing.STATUS_WITHDRAWN:
        return listing
    listing.status = ResaleListing.STATUS_WITHDRAWN
    listing.withdrawn_at = now()
    listing.reserved_until = None
    listing.reserved_session = ''
    listing.save(update_fields=['status', 'withdrawn_at', 'reserved_until', 'reserved_session', 'updated'])
    listing.seller_order.log_action(
        'eventyay.plugins.resale.listing.withdrawn',
        data={'listing': listing.pk, 'position': listing.position_id},
    )
    return listing


@transaction.atomic
def release_expired_reservations(event=None) -> int:
    qs = ResaleListing.objects.select_for_update().filter(
        status=ResaleListing.STATUS_RESERVED,
        reserved_until__lt=now(),
    )
    if event is not None:
        qs = qs.filter(event=event)
    released = 0
    for listing in qs:
        listing.status = ResaleListing.STATUS_AVAILABLE
        listing.reserved_until = None
        listing.reserved_session = ''
        listing.buyer_order = None
        listing.save(
            update_fields=['status', 'reserved_until', 'reserved_session', 'buyer_order', 'updated']
        )
        released += 1
    return released


@transaction.atomic
def reserve_listing(*, listing: ResaleListing, session_key: str) -> ResaleListing:
    release_expired_reservations(listing.event)
    listing = ResaleListing.objects.select_for_update().get(pk=listing.pk)
    if not marketplace_is_open(listing.event):
        raise ResaleError(_('The ticket marketplace is not open.'))
    if listing.status == ResaleListing.STATUS_RESERVED and listing.reserved_session == session_key:
        listing.reserved_until = now() + reservation_ttl(listing.event)
        listing.save(update_fields=['reserved_until', 'updated'])
        return listing
    if listing.status != ResaleListing.STATUS_AVAILABLE:
        raise ResaleError(_('This ticket is no longer available.'))
    listing.status = ResaleListing.STATUS_RESERVED
    listing.reserved_session = session_key or ''
    listing.reserved_until = now() + reservation_ttl(listing.event)
    listing.save(update_fields=['status', 'reserved_session', 'reserved_until', 'updated'])
    listing.seller_order.log_action(
        'eventyay.plugins.resale.listing.reserved',
        data={'listing': listing.pk, 'until': listing.reserved_until.isoformat()},
    )
    return listing


@transaction.atomic
def complete_resale(*, listing: ResaleListing, buyer_order: Order, buyer_position: OrderPosition) -> ResaleListing:
    """Invalidate the seller ticket and refund the seller after buyer payment."""
    listing = (
        ResaleListing.objects.select_for_update()
        .select_related('position', 'seller_order', 'event')
        .get(pk=listing.pk)
    )
    if listing.status == ResaleListing.STATUS_SOLD:
        return listing
    if listing.status not in (ResaleListing.STATUS_RESERVED, ResaleListing.STATUS_AVAILABLE):
        raise ResaleError(_('This listing cannot be completed.'))

    seller_position = listing.position
    if seller_position.canceled:
        raise ResaleError(_('The original ticket is already cancelled.'))

    # Cancel the seller's position so the old QR is invalid and quota stays balanced
    # with the newly created buyer ticket.
    ocm = OrderChangeManager(listing.seller_order, notify=False)
    ocm.cancel(seller_position)
    try:
        ocm.commit(check_quotas=False)
    except (OrderError, Quota.QuotaExceededException) as exc:
        raise ResaleError(str(exc)) from exc

    fee, payout = calculate_seller_payout(listing.event, listing.price)
    listing.fee_amount = fee
    listing.seller_payout = payout
    listing.status = ResaleListing.STATUS_SOLD
    listing.sold_at = now()
    listing.buyer_order = buyer_order
    listing.buyer_position = buyer_position
    listing.reserved_until = None
    listing.reserved_session = ''
    listing.refund_status = ResaleListing.REFUND_PENDING
    listing.save()

    listing.seller_order.log_action(
        'eventyay.plugins.resale.listing.sold',
        data={
            'listing': listing.pk,
            'buyer_order': buyer_order.code,
            'fee': str(fee),
            'payout': str(payout),
        },
    )
    buyer_order.log_action(
        'eventyay.plugins.resale.purchase.completed',
        data={'listing': listing.pk, 'seller_order': listing.seller_order.code},
    )

    # Partial refund of the seller payout on the original order.
    try:
        _refund_seller(listing)
    except Exception:
        logger.exception('Resale refund failed for listing %s', listing.pk)
        listing.refund_status = ResaleListing.REFUND_FAILED
        listing.save(update_fields=['refund_status', 'updated'])
        listing.seller_order.log_action(
            'eventyay.plugins.resale.refund.failed',
            data={'listing': listing.pk, 'payout': str(payout)},
        )
    return listing


def _refund_seller(listing: ResaleListing) -> None:
    order = listing.seller_order
    amount = listing.seller_payout
    if amount <= Decimal('0.00'):
        listing.refund_status = ResaleListing.REFUND_DONE
        listing.save(update_fields=['refund_status', 'updated'])
        return

    payment = order.payments.filter(state=OrderPayment.PAYMENT_STATE_CONFIRMED).order_by(
        '-payment_date', '-pk'
    ).first()
    refund = order.refunds.create(
        payment=payment,
        source=OrderRefund.REFUND_SOURCE_ADMIN,
        state=OrderRefund.REFUND_STATE_CREATED,
        amount=amount,
        comment=_('Ticket resale payout (fee {fee} retained)').format(fee=listing.fee_amount),
        provider=payment.provider if payment else 'manual',
    )
    listing.refund = refund
    listing.save(update_fields=['refund', 'updated'])

    if payment is not None:
        try:
            payment.payment_provider.execute_refund(refund)
        except Exception:
            refund.state = OrderRefund.REFUND_STATE_FAILED
            refund.save(update_fields=['state'])
            raise
        refund.refresh_from_db()
        if refund.state in (OrderRefund.REFUND_STATE_DONE, OrderRefund.REFUND_STATE_TRANSIT):
            listing.refund_status = ResaleListing.REFUND_DONE
        elif refund.state == OrderRefund.REFUND_STATE_FAILED:
            listing.refund_status = ResaleListing.REFUND_FAILED
        else:
            listing.refund_status = ResaleListing.REFUND_PENDING
    else:
        refund.state = OrderRefund.REFUND_STATE_CREATED
        refund.save(update_fields=['state'])
        listing.refund_status = ResaleListing.REFUND_PENDING

    listing.save(update_fields=['refund_status', 'updated'])
    listing.seller_order.log_action(
        'eventyay.plugins.resale.refund.created',
        data={'listing': listing.pk, 'refund': refund.pk, 'amount': str(amount)},
    )


def available_listings_qs(event):
    release_expired_reservations(event)
    return (
        ResaleListing.objects.filter(event=event, status=ResaleListing.STATUS_AVAILABLE)
        .select_related('position', 'position__product', 'position__variation')
        .order_by('price', 'created')
    )


def seller_listings_for_order(order: Order):
    return (
        ResaleListing.objects.filter(seller_order=order)
        .exclude(status=ResaleListing.STATUS_WITHDRAWN)
        .select_related('position', 'position__product')
    )
