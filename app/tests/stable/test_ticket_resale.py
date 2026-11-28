"""Ticket resale marketplace (#7669) — core eligibility, fees, list/withdraw/reserve."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Order, OrderPayment, OrderPosition, Product, Quota, Voucher
from eventyay.plugins.resale.models import ResaleListing
from eventyay.plugins.resale.services import (
    RESALE_ROLE_BUYER,
    RESALE_ROLE_SELLER,
    ResaleError,
    calculate_fee,
    calculate_seller_payout,
    complete_resale,
    create_listing,
    is_position_eligible,
    marketplace_is_open,
    release_expired_reservations,
    reserve_listing,
    withdraw_listing,
)


@pytest.fixture
def resale_event(event):
    with scope(organizer=event.organizer, event=event):
        event.plugins = (event.plugins + ',eventyay.plugins.resale').strip(',')
        event.save(update_fields=['plugins'])
        event.settings.set('resale_enabled', True)
        event.settings.set('resale_fee_mode', 'fixed')
        event.settings.set('resale_fee_fixed', Decimal('5.00'))
        event.settings.set('resale_reservation_minutes', 30)
    return event


@pytest.fixture
def ticket_product(resale_event):
    with scope(organizer=resale_event.organizer, event=resale_event):
        product = Product.objects.create(
            event=resale_event,
            name='Congress Ticket',
            default_price=Decimal('200.00'),
            admission=True,
        )
        quota = Quota.objects.create(event=resale_event, name='Tickets', size=10)
        quota.products.add(product)
        return product


@pytest.fixture
def paid_position(resale_event, ticket_product):
    with scope(organizer=resale_event.organizer, event=resale_event):
        order = Order.objects.create(
            event=resale_event,
            status=Order.STATUS_PAID,
            expires=now() + timedelta(days=1),
            total=Decimal('200.00'),
            code='SELLER1',
            email='seller@example.com',
            datetime=now(),
            locale='en',
        )
        return OrderPosition.objects.create(
            order=order,
            product=ticket_product,
            price=Decimal('200.00'),
            attendee_name_parts={'_legacy': 'Seller Person'},
            attendee_email='seller@example.com',
        )


@pytest.mark.django_db
def test_marketplace_disabled_by_default(event):
    with scope(organizer=event.organizer, event=event):
        event.plugins = (event.plugins + ',eventyay.plugins.resale').strip(',')
        event.save(update_fields=['plugins'])
        assert marketplace_is_open(event) is False


@pytest.mark.django_db
def test_marketplace_open_when_enabled(resale_event):
    with scope(organizer=resale_event.organizer, event=resale_event):
        assert marketplace_is_open(resale_event) is True
        resale_event.settings.set('resale_suspended', True)
        assert marketplace_is_open(resale_event) is False


@pytest.mark.django_db
def test_fee_calculation_fixed_and_percent(resale_event):
    with scope(organizer=resale_event.organizer, event=resale_event):
        assert calculate_fee(resale_event, Decimal('200.00')) == Decimal('5.00')
        fee, payout = calculate_seller_payout(resale_event, Decimal('200.00'))
        assert fee == Decimal('5.00')
        assert payout == Decimal('195.00')

        resale_event.settings.set('resale_fee_mode', 'percent')
        resale_event.settings.set('resale_fee_percent', Decimal('10.00'))
        assert calculate_fee(resale_event, Decimal('200.00')) == Decimal('20.00')


@pytest.mark.django_db
def test_create_listing_and_reject_overprice(resale_event, paid_position, ticket_product):
    with scope(organizer=resale_event.organizer, event=resale_event):
        listing = create_listing(event=resale_event, position=paid_position, price=Decimal('180.00'))
        assert listing.status == ResaleListing.STATUS_AVAILABLE
        assert listing.fee_amount == Decimal('5.00')
        assert listing.seller_payout == Decimal('175.00')

        other_order = Order.objects.create(
            event=resale_event,
            status=Order.STATUS_PAID,
            expires=now() + timedelta(days=1),
            total=Decimal('200.00'),
            code='SELLER2',
            email='seller2@example.com',
            datetime=now(),
            locale='en',
        )
        other_pos = OrderPosition.objects.create(
            order=other_order,
            product=ticket_product,
            price=Decimal('200.00'),
        )
        with pytest.raises(ResaleError):
            create_listing(event=resale_event, position=other_pos, price=Decimal('250.00'))


@pytest.mark.django_db
def test_duplicate_listing_blocked(resale_event, paid_position):
    with scope(organizer=resale_event.organizer, event=resale_event):
        create_listing(event=resale_event, position=paid_position, price=Decimal('200.00'))
        ok, _reason = is_position_eligible(resale_event, paid_position)
        assert ok is False
        with pytest.raises(ResaleError):
            create_listing(event=resale_event, position=paid_position, price=Decimal('200.00'))


@pytest.mark.django_db
def test_withdraw_and_reserve_flow(resale_event, paid_position):
    with scope(organizer=resale_event.organizer, event=resale_event):
        listing = create_listing(event=resale_event, position=paid_position, price=Decimal('200.00'))
        reserved = reserve_listing(listing=listing, session_key='buyer-session')
        assert reserved.status == ResaleListing.STATUS_RESERVED
        with pytest.raises(ResaleError):
            withdraw_listing(listing=reserved)

        reserved.reserved_until = now() - timedelta(minutes=1)
        reserved.save(update_fields=['reserved_until'])
        assert release_expired_reservations(resale_event) == 1
        reserved.refresh_from_db()
        assert reserved.status == ResaleListing.STATUS_AVAILABLE

        withdraw_listing(listing=reserved)
        reserved.refresh_from_db()
        assert reserved.status == ResaleListing.STATUS_WITHDRAWN


@pytest.mark.django_db
def test_checked_in_ticket_not_eligible(resale_event, paid_position):
    from eventyay.base.models import Checkin, CheckinList

    with scope(organizer=resale_event.organizer, event=resale_event):
        cl = CheckinList.objects.create(event=resale_event, name='Gate', all_products=True)
        Checkin.objects.create(position=paid_position, list=cl)
        ok, reason = is_position_eligible(resale_event, paid_position)
        assert ok is False
        assert 'Checked-in' in str(reason)


@pytest.mark.django_db
def test_product_filter_restricts_eligibility(resale_event, paid_position, ticket_product):
    with scope(organizer=resale_event.organizer, event=resale_event):
        other = Product.objects.create(
            event=resale_event,
            name='Other',
            default_price=Decimal('10.00'),
            admission=True,
        )
        resale_event.settings.set('resale_products', [str(other.pk)])
        ok, _reason = is_position_eligible(resale_event, paid_position)
        assert ok is False

        resale_event.settings.set('resale_products', [str(ticket_product.pk)])
        ok, _reason = is_position_eligible(resale_event, paid_position)
        assert ok is True


@pytest.mark.django_db
def test_non_admission_product_not_eligible(resale_event, paid_position):
    with scope(organizer=resale_event.organizer, event=resale_event):
        paid_position.product.admission = False
        paid_position.product.save(update_fields=['admission'])
        ok, reason = is_position_eligible(resale_event, paid_position)
        assert ok is False
        assert 'admission' in str(reason).lower()


@pytest.mark.django_db
def test_withdrawn_listing_can_be_relisted(resale_event, paid_position):
    with scope(organizer=resale_event.organizer, event=resale_event):
        listing = create_listing(event=resale_event, position=paid_position, price=Decimal('200.00'))
        withdraw_listing(listing=listing)
        relisted = create_listing(event=resale_event, position=paid_position, price=Decimal('180.00'))
        assert relisted.pk == listing.pk
        assert relisted.status == ResaleListing.STATUS_AVAILABLE
        assert relisted.price == Decimal('180.00')
        assert ResaleListing.objects.filter(position=paid_position).count() == 1


@pytest.mark.django_db
def test_complete_resale_rejects_expired_reservation(resale_event, paid_position, ticket_product):
    with scope(organizer=resale_event.organizer, event=resale_event):
        listing = create_listing(event=resale_event, position=paid_position, price=Decimal('200.00'))
        reserve_listing(listing=listing, session_key='buyer-a')
        listing.reserved_until = now() - timedelta(minutes=1)
        listing.save(update_fields=['reserved_until'])
        release_expired_reservations(resale_event)
        listing.refresh_from_db()
        assert listing.status == ResaleListing.STATUS_AVAILABLE

        buyer_order = Order.objects.create(
            event=resale_event,
            status=Order.STATUS_PAID,
            expires=now() + timedelta(days=1),
            total=Decimal('200.00'),
            code='BUYER1',
            email='buyer@example.com',
            datetime=now(),
            locale='en',
        )
        buyer_pos = OrderPosition.objects.create(
            order=buyer_order,
            product=ticket_product,
            price=Decimal('200.00'),
        )
        with pytest.raises(ResaleError):
            complete_resale(listing=listing, buyer_order=buyer_order, buyer_position=buyer_pos)


@pytest.mark.django_db
def test_release_reservation_only_clears_own_session(resale_event, paid_position):
    from eventyay.plugins.resale.services import release_reservation

    with scope(organizer=resale_event.organizer, event=resale_event):
        listing = create_listing(event=resale_event, position=paid_position, price=Decimal('200.00'))
        reserve_listing(listing=listing, session_key='buyer-a')
        listing.refresh_from_db()
        assert listing.status == ResaleListing.STATUS_RESERVED

        # A different session must not clear buyer-a's hold.
        release_reservation(listing=listing, session_key='buyer-b')
        listing.refresh_from_db()
        assert listing.status == ResaleListing.STATUS_RESERVED
        assert listing.reserved_session == 'buyer-a'

        release_reservation(listing=listing, session_key='buyer-a')
        listing.refresh_from_db()
        assert listing.status == ResaleListing.STATUS_AVAILABLE
        assert listing.reserved_session == ''


@pytest.mark.django_db
def test_refunded_ticket_not_eligible(resale_event, paid_position):
    from eventyay.base.models import OrderRefund

    with scope(organizer=resale_event.organizer, event=resale_event):
        paid_position.order.refunds.create(
            state=OrderRefund.REFUND_STATE_DONE,
            source=OrderRefund.REFUND_SOURCE_ADMIN,
            amount=Decimal('200.00'),
            provider='manual',
        )
        ok, reason = is_position_eligible(resale_event, paid_position)
        assert ok is False
        assert 'Refunded' in str(reason)


@pytest.mark.django_db
def test_complete_resale_tags_seller_and_buyer_orders(resale_event, paid_position, ticket_product):
    with scope(organizer=resale_event.organizer, event=resale_event):
        seller_order = paid_position.order
        OrderPayment.objects.create(
            order=seller_order,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('200.00'),
            provider='manual',
            payment_date=now(),
        )
        listing = create_listing(event=resale_event, position=paid_position, price=Decimal('200.00'))
        reserve_listing(listing=listing, session_key='buyer-a')
        listing.refresh_from_db()

        voucher = Voucher.objects.create(
            event=resale_event,
            code='RESALEBUY',
            max_usages=1,
            redeemed=1,
            valid_until=now() + timedelta(hours=1),
            allow_ignore_quota=True,
            product=ticket_product,
            price_mode='set',
            value=Decimal('200.00'),
            tag=f'resale:{listing.pk}',
        )
        buyer_order = Order.objects.create(
            event=resale_event,
            status=Order.STATUS_PAID,
            expires=now() + timedelta(days=1),
            total=Decimal('200.00'),
            code='BUYER2',
            email='buyer2@example.com',
            datetime=now(),
            locale='en',
        )
        buyer_pos = OrderPosition.objects.create(
            order=buyer_order,
            product=ticket_product,
            price=Decimal('200.00'),
            voucher=voucher,
        )

        complete_resale(listing=listing, buyer_order=buyer_order, buyer_position=buyer_pos)

        seller_order = paid_position.order
        seller_order.refresh_from_db()
        buyer_order.refresh_from_db()
        listing.refresh_from_db()

        assert listing.status == ResaleListing.STATUS_SOLD
        assert listing.fee_amount == Decimal('5.00')
        assert listing.seller_payout == Decimal('195.00')
        # Full-price resale: retain only the processing fee.
        assert seller_order.total == Decimal('5.00')
        assert seller_order.meta_info_data['resale_role'] == RESALE_ROLE_SELLER
        assert seller_order.meta_info_data['resale_listing_id'] == listing.pk
        assert seller_order.meta_info_data['resale_related_order'] == buyer_order.code
        assert buyer_order.meta_info_data['resale_role'] == RESALE_ROLE_BUYER
        assert buyer_order.meta_info_data['resale_listing_id'] == listing.pk
        assert buyer_order.meta_info_data['resale_related_order'] == seller_order.code


@pytest.mark.django_db
def test_complete_resale_discounted_retains_paid_minus_payout(resale_event, paid_position, ticket_product):
    """Discounted asking price: retain paid_credit - payout, not only the fee."""
    with scope(organizer=resale_event.organizer, event=resale_event):
        seller_order = paid_position.order
        OrderPayment.objects.create(
            order=seller_order,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('200.00'),
            provider='manual',
            payment_date=now(),
        )
        listing = create_listing(event=resale_event, position=paid_position, price=Decimal('150.00'))
        reserve_listing(listing=listing, session_key='buyer-a')
        listing.refresh_from_db()

        voucher = Voucher.objects.create(
            event=resale_event,
            code='RESALEDISC',
            max_usages=1,
            redeemed=1,
            valid_until=now() + timedelta(hours=1),
            allow_ignore_quota=True,
            product=ticket_product,
            price_mode='set',
            value=Decimal('150.00'),
            tag=f'resale:{listing.pk}',
        )
        buyer_order = Order.objects.create(
            event=resale_event,
            status=Order.STATUS_PAID,
            expires=now() + timedelta(days=1),
            total=Decimal('150.00'),
            code='BUYER3',
            email='buyer3@example.com',
            datetime=now(),
            locale='en',
        )
        buyer_pos = OrderPosition.objects.create(
            order=buyer_order,
            product=ticket_product,
            price=Decimal('150.00'),
            voucher=voucher,
        )

        complete_resale(listing=listing, buyer_order=buyer_order, buyer_position=buyer_pos)

        seller_order.refresh_from_db()
        listing.refresh_from_db()

        assert listing.fee_amount == Decimal('5.00')
        assert listing.seller_payout == Decimal('145.00')
        # paid 200 - payout 145 = retain 55 (discount 50 + fee 5)
        assert seller_order.total == Decimal('55.00')
        assert seller_order.status == Order.STATUS_PAID
