from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.models import Order, OrderPayment, OrderPosition, OrderRefund, Quota
from eventyay.base.services.orders import OrderChangeManager, OrderError, _cancel_order

from .models import ResaleListing
from .settings import (
    FEE_MODE_FIXED,
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


def is_position_eligible(
    event,
    position: OrderPosition,
    *,
    ignore_listing: ResaleListing | None = None,
    require_open: bool = True,
) -> tuple[bool, str]:
    """Return (ok, reason) for whether a position may be listed or traded."""
    if require_open and not marketplace_is_open(event):
        return False, _('The ticket marketplace is not open.')
    if position.canceled:
        return False, _('This ticket has been cancelled.')
    if position.addon_to_id:
        return False, _('Add-on products cannot be resold separately.')
    if position.addons.filter(canceled=False).exists():
        return False, _('Tickets with active add-ons cannot be resold yet.')
    if position.seat_id:
        return False, _('Seated tickets cannot be resold yet.')
    if not position.product.admission:
        return False, _('Only admission tickets can be listed for resale.')
    if position.order.status not in (Order.STATUS_PAID, Order.STATUS_PENDING):
        return False, _('Only paid or pending orders can be resold.')
    if position.order.status == Order.STATUS_PENDING and position.order.pending_sum > 0:
        return False, _('This order is not fully paid.')
    if position.order.status != Order.STATUS_PAID:
        return False, _('Only paid tickets can be listed for resale.')
    refund_total = position.order.refunds.filter(
        state__in=(
            OrderRefund.REFUND_STATE_DONE,
            OrderRefund.REFUND_STATE_TRANSIT,
            OrderRefund.REFUND_STATE_CREATED,
        )
    ).exists()
    if refund_total and position.order.payment_refund_sum < position.price:
        return False, _('Refunded tickets cannot be resold.')
    product_ids = eligible_product_ids(event)
    if product_ids and position.product_id not in product_ids:
        return False, _('This ticket type is not eligible for resale.')
    if position_has_checkin(position):
        return False, _('Checked-in tickets cannot be resold.')
    listing = getattr(position, 'resale_listing', None)
    if listing is not None and (ignore_listing is None or listing.pk != ignore_listing.pk):
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
        existing = getattr(position, 'resale_listing', None)
        if existing is not None and existing.status == ResaleListing.STATUS_WITHDRAWN:
            listing = ResaleListing.objects.select_for_update().get(pk=existing.pk)
            listing.price = price
            listing.original_price = max_price
            listing.fee_amount = fee
            listing.seller_payout = payout
            listing.status = ResaleListing.STATUS_AVAILABLE
            listing.withdrawn_at = None
            listing.reserved_until = None
            listing.reserved_session = ''
            listing.buyer_order = None
            listing.buyer_position = None
            listing.refund = None
            listing.refund_status = ResaleListing.REFUND_NONE
            listing.sold_at = None
            listing.save()
        else:
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
def release_reservation(*, listing: ResaleListing) -> ResaleListing:
    """Return a reserved listing to the available pool (e.g. after a failed cart add)."""
    listing = ResaleListing.objects.select_for_update().get(pk=listing.pk)
    if listing.status != ResaleListing.STATUS_RESERVED:
        return listing
    listing.status = ResaleListing.STATUS_AVAILABLE
    listing.reserved_until = None
    listing.reserved_session = ''
    listing.buyer_order = None
    listing.save(
        update_fields=['status', 'reserved_until', 'reserved_session', 'buyer_order', 'updated']
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
    listing = (
        ResaleListing.objects.select_for_update()
        .select_related('position', 'position__product', 'position__order', 'event')
        .get(pk=listing.pk)
    )
    if not marketplace_is_open(listing.event):
        raise ResaleError(_('The ticket marketplace is not open.'))
    if listing.status == ResaleListing.STATUS_RESERVED and listing.reserved_session == session_key:
        ok, reason = is_position_eligible(listing.event, listing.position, ignore_listing=listing)
        if not ok:
            raise ResaleError(reason)
        listing.reserved_until = now() + reservation_ttl(listing.event)
        listing.save(update_fields=['reserved_until', 'updated'])
        return listing
    if listing.status != ResaleListing.STATUS_AVAILABLE:
        raise ResaleError(_('This ticket is no longer available.'))
    ok, reason = is_position_eligible(listing.event, listing.position, ignore_listing=listing)
    if not ok:
        raise ResaleError(reason)
    listing.status = ResaleListing.STATUS_RESERVED
    listing.reserved_session = session_key or ''
    listing.reserved_until = now() + reservation_ttl(listing.event)
    listing.save(update_fields=['status', 'reserved_session', 'reserved_until', 'updated'])
    listing.seller_order.log_action(
        'eventyay.plugins.resale.listing.reserved',
        data={'listing': listing.pk, 'until': listing.reserved_until.isoformat()},
    )
    return listing


def _buyer_owns_listing(listing: ResaleListing, buyer_order: Order, buyer_position: OrderPosition) -> bool:
    expected = f'resale:{listing.pk}'
    if buyer_position.voucher and (buyer_position.voucher.tag or '') == expected:
        return True
    return buyer_order.positions.filter(canceled=False, voucher__tag=expected).exists()


@transaction.atomic
def complete_resale(*, listing: ResaleListing, buyer_order: Order, buyer_position: OrderPosition) -> ResaleListing:
    """Invalidate the seller ticket and refund the seller after buyer payment."""
    listing = (
        ResaleListing.objects.select_for_update()
        .select_related('position', 'position__product', 'position__order', 'seller_order', 'event')
        .get(pk=listing.pk)
    )
    if listing.status == ResaleListing.STATUS_SOLD:
        if listing.buyer_order_id == buyer_order.pk:
            return listing
        raise ResaleError(_('This listing has already been sold to another buyer.'))

    # Only the order that holds the active reservation may complete the sale.
    # Available/expired listings must not be claimed by a late payment.
    if listing.status != ResaleListing.STATUS_RESERVED:
        raise ResaleError(_('This reservation is no longer valid for this purchase.'))
    if not _buyer_owns_listing(listing, buyer_order, buyer_position):
        raise ResaleError(_('This order does not hold the reservation for this listing.'))

    seller_position = listing.position
    ok, reason = is_position_eligible(
        listing.event,
        seller_position,
        ignore_listing=listing,
        require_open=False,
    )
    if not ok:
        raise ResaleError(reason)
    if seller_position.canceled:
        raise ResaleError(_('The original ticket is already cancelled.'))

    # Invalidate the seller ticket. OrderChangeManager refuses to empty an order,
    # so single-ticket seller orders are cancelled wholesale instead.
    remaining = (
        listing.seller_order.positions.filter(canceled=False).exclude(pk=seller_position.pk).count()
    )
    try:
        if remaining == 0:
            _cancel_order(listing.seller_order, send_mail=True, cancel_invoice=True)
            listing.seller_order.refresh_from_db()
        else:
            ocm = OrderChangeManager(listing.seller_order, notify=False)
            ocm.cancel(seller_position)
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

    # Prefer a confirmed payment that still has enough refundable balance.
    payment = None
    for candidate in order.payments.filter(state=OrderPayment.PAYMENT_STATE_CONFIRMED).order_by(
        '-payment_date', '-pk'
    ):
        available = candidate.amount - candidate.refunded_amount
        if available >= amount:
            payment = candidate
            break
    if payment is None:
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
