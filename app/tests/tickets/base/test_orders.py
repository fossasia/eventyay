import json
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.core import mail as djmail
from django.test import TestCase
from django.utils.timezone import make_aware, now
from django_countries.fields import Country
from django_scopes import scope

from eventyay.base.decimal import round_decimal
from eventyay.base.models import (
    CartPosition,
    Event,
    InvoiceAddress,
    Product as Item,
    Order,
    OrderPosition,
    Organizer,
    SeatingPlan,
)
from eventyay.base.models.orders import OrderFee, OrderPayment, OrderRefund
from eventyay.base.models.product import SubEventProduct as SubEventItem
from eventyay.base.payment import FreeOrderProvider
from eventyay.base.reldate import RelativeDate, RelativeDateWrapper
from eventyay.base.services.invoices import generate_invoice
from eventyay.base.services.orders import (
    OrderChangeManager,
    OrderError,
    _cancel_order_positions,
    _check_date,
    _create_order,
    approve_order,
    cancel_order,
    cancel_order_positions,
    deny_order,
    expire_orders,
    reactivate_order,
    send_download_reminders,
    send_expiry_warnings,
)
from eventyay.plugins.banktransfer.payment import BankTransfer
from tests.testutils.scope import classscope
from tests.tickets.testdummy.signals import FoobazSalesChannel


@pytest.fixture(scope='function')
def event():
    o = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='eventyay.plugins.banktransfer',
    )
    with scope(organizer=o):
        yield event


def create_paid_cancellation_order(event, code, ticket_prices, fees=(), provider='manual'):
    product = Item.objects.create(event=event, name='Ticket', default_price=10, admission=True)
    total = sum(ticket_prices, Decimal('0.00')) + sum((value for _fee_type, value in fees), Decimal('0.00'))
    order = Order.objects.create(
        code=code,
        event=event,
        status=Order.STATUS_PAID,
        locale='en',
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=total,
    )
    positions = [
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=price,
            positionid=index,
        )
        for index, price in enumerate(ticket_prices, start=1)
    ]
    for fee_type, value in fees:
        order.fees.create(fee_type=fee_type, value=value)
    order.payments.create(
        amount=total,
        state=OrderPayment.PAYMENT_STATE_CONFIRMED,
        provider=provider,
    )
    return order, positions


@pytest.mark.django_db
def test_partial_cancellation_sufficient_payment_credit(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('2.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'PARTIAL-CREDIT',
            [Decimal('10.00'), Decimal('10.00')],
        )

        _cancel_order_positions(order.pk, [positions[0].pk])
        order.refresh_from_db()

        assert order.status == Order.STATUS_PAID
        assert order.user_existing_cancellation_fee == Decimal('2.00')
        assert order.payment_refund_sum == Decimal('20.00')


@pytest.mark.django_db
def test_partial_cancellation_insufficient_payment_credit(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('0')
        event.settings.cancel_allow_user_paid_keep = Decimal('25.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'OVER-CREDIT',
            [Decimal('5.00'), Decimal('5.00'), Decimal('5.00')],
        )
        order.refunds.create(
            source=OrderRefund.REFUND_SOURCE_BUYER,
            state=OrderRefund.REFUND_STATE_DONE,
            amount=Decimal('10.00'),
            provider='manual',
            execution_date=now(),
        )
        order.refresh_from_db()
        assert order.payment_refund_sum == Decimal('5.00')

        _cancel_order_positions(order.pk, [positions[0].pk])
        order.refresh_from_db()
        assert order.user_existing_cancellation_fee == Decimal('5.00')

        with pytest.raises(
            OrderError,
            match='The cancellation fee cannot be higher than the payment credit of this order.',
        ):
            _cancel_order_positions(order.pk, [positions[1].pk])

        order.refresh_from_db()
        assert order.user_existing_cancellation_fee == Decimal('5.00')
        positions[1].refresh_from_db()
        assert not positions[1].canceled
        assert order.status == Order.STATUS_PAID


@pytest.mark.django_db
def test_partial_cancellation_after_existing_refund(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('0')
        event.settings.cancel_allow_user_paid_keep = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'REFUND-CREDIT',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        order.refunds.create(
            source=OrderRefund.REFUND_SOURCE_BUYER,
            state=OrderRefund.REFUND_STATE_DONE,
            amount=Decimal('25.00'),
            provider='manual',
            execution_date=now(),
        )
        order.refresh_from_db()
        assert order.payment_refund_sum == Decimal('5.00')

        _cancel_order_positions(order.pk, [positions[0].pk])
        order.refresh_from_db()
        assert order.user_existing_cancellation_fee == Decimal('3.33')

        with pytest.raises(OrderError):
            _cancel_order_positions(order.pk, [positions[1].pk])

        order.refresh_from_db()
        assert order.user_existing_cancellation_fee == Decimal('3.33')


@pytest.mark.django_db
def test_partial_then_full_cancellation_uses_cumulative_fee(event):
    with scope(organizer=event.organizer, event=event):
        product = Item.objects.create(
            event=event,
            name='Ticket',
            default_price=Decimal('10.00'),
            admission=True,
        )
        order = Order.objects.create(
            code='CUMULATIVE',
            event=event,
            status=Order.STATUS_PAID,
            locale='en',
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('20.00'),
        )
        first = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('10.00'),
            positionid=1,
        )
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('10.00'),
            positionid=2,
        )
        order.payments.create(
            amount=Decimal('20.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='manual',
        )
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('2.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order = Order.objects.get(pk=order.pk)

        _cancel_order_positions(order.pk, [first.pk])
        order.refresh_from_db()
        assert order.user_existing_cancellation_fee == Decimal('2.00')
        assert order.customer_cancellation_summary() is not None

        cancellation_fee = order.user_cancel_fee
        assert cancellation_fee == Decimal('4.00')
        cancel_order(order.pk, cancellation_fee=cancellation_fee)
        order.refresh_from_db()
        assert order.total == Decimal('4.00')


@pytest.mark.django_db
def test_zero_fee_partial_records_cumulative_ticket_value(event):
    with scope(organizer=event.organizer, event=event):
        product = Item.objects.create(event=event, name='Ticket', default_price=10, admission=True)
        order = Order.objects.create(
            code='ZERO-FEE',
            event=event,
            status=Order.STATUS_PAID,
            locale='en',
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('10.00'),
        )
        first = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('0.00'),
            positionid=1,
        )
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('10.00'),
            positionid=2,
        )
        order.payments.create(
            amount=Decimal('10.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='manual',
        )
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('0.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order = Order.objects.get(pk=order.pk)

        _cancel_order_positions(order.pk, [first.pk])
        order.refresh_from_db()
        assert order.user_existing_cancellation_fee == Decimal('0.00')
        summary = order.customer_cancellation_summary()
        assert summary is not None
        assert summary[0] == Decimal('0.00')

        assert order.user_cancel_fee == Decimal('1.00')


@pytest.mark.django_db
def test_zero_fee_generic_cancellation_clears_customer_metadata(event):
    with scope(organizer=event.organizer, event=event):
        product = Item.objects.create(event=event, name='Ticket', default_price=10, admission=True)
        order = Order.objects.create(
            code='GENERIC-ZERO',
            event=event,
            status=Order.STATUS_PAID,
            locale='en',
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('10.00'),
        )
        first = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('0.00'),
            positionid=1,
        )
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('10.00'),
            positionid=2,
        )
        order.payments.create(
            amount=Decimal('10.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='manual',
        )
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('0.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order = Order.objects.get(pk=order.pk)

        _cancel_order_positions(order.pk, [first.pk])
        cancel_order(order.pk, cancellation_fee=Decimal('0.00'), cancel_invoice=False)
        order.refresh_from_db()
        assert order.status == Order.STATUS_CANCELED

        for position in order.all_positions.all():
            assert Order.CUSTOMER_CANCELLATION_META_KEY not in position.meta_info_data
        assert order.customer_cancellation_summary() is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    'bad_value',
    ['NaN', 'Infinity', '-Infinity', 'invalid', '-1.00', '999999999999999999999999999999'],
)
def test_malformed_cancellation_metadata_uses_fallback(event, bad_value):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('2')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'BAD-META',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])
        order = Order.objects.get(pk=order.pk)
        position = order.all_positions.get(pk=positions[0].pk)
        assert order.customer_cancellation_summary() is not None

        metadata = position.meta_info_data
        metadata[Order.CUSTOMER_CANCELLATION_META_KEY]['ticket_value'] = bad_value
        position.meta_info = json.dumps(metadata)
        position.save(update_fields=['meta_info'])

        assert order.customer_cancellation_summary() is None

        with pytest.raises(
            OrderError,
            match='The cancellation history for this order is missing or invalid.',
        ):
            _cancel_order_positions(order.pk, [positions[1].pk])


@pytest.mark.django_db
def test_missing_cancellation_metadata_rejects_next_partial(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('2')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'MISSING-HISTORY',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        order = Order.objects.get(pk=order.pk)
        position = order.all_positions.get(pk=positions[0].pk)
        metadata = position.meta_info_data
        metadata.pop(Order.CUSTOMER_CANCELLATION_META_KEY)
        position.meta_info = json.dumps(metadata)
        position.save(update_fields=['meta_info'])

        with pytest.raises(
            OrderError,
            match='The cancellation history for this order is missing or invalid.',
        ):
            _cancel_order_positions(order.pk, [positions[1].pk])


@pytest.mark.django_db
def test_cancellation_history_is_isolated_by_event(event):
    with scope(organizer=event.organizer):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('2')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'EVENT-CURRENT',
            [Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        other_event = Event.objects.create(
            organizer=event.organizer,
            name='Other event',
            slug='other-event',
            date_from=now(),
        )
        other_product = Item.objects.create(
            event=other_event,
            name='Other ticket',
            default_price=Decimal('50.00'),
            admission=True,
        )
        other_order = Order.objects.create(
            code=order.code,
            event=other_event,
            status=Order.STATUS_PAID,
            locale='en',
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('50.00'),
        )
        other_position = OrderPosition.objects.create(
            order=other_order,
            product=other_product,
            price=Decimal('50.00'),
            positionid=1,
            canceled=True,
        )
        other_position.meta_info = json.dumps({
            Order.CUSTOMER_CANCELLATION_META_KEY: {
                'order_code': order.code,
                'ticket_value': '50.00',
                'fee_value': '12.50',
                'original_ticket_value': '50.00',
                'original_order_total': '50.00',
                'retained_extra_fees': '0.00',
                'settings': order.customer_cancellation_settings(),
            }
        })
        other_position.save(update_fields=['meta_info'])

        order = Order.objects.get(pk=order.pk)
        assert order.customer_cancellation_summary() is not None
        assert order.customer_cancellation_summary()[0] == Decimal('10.00')


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('fee_types', 'expected_full_fee'),
    [
        ((OrderFee.FEE_TYPE_PAYMENT,), Decimal('7.00')),
        ((OrderFee.FEE_TYPE_SHIPPING,), Decimal('6.00')),
        ((OrderFee.FEE_TYPE_SERVICE,), Decimal('5.00')),
        (
            (
                OrderFee.FEE_TYPE_PAYMENT,
                OrderFee.FEE_TYPE_SHIPPING,
                OrderFee.FEE_TYPE_SERVICE,
            ),
            Decimal('10.00'),
        ),
    ],
)
def test_keep_existing_fees_agrees_full_and_staged(event, fee_types, expected_full_fee):
    with scope(organizer=event.organizer, event=event):
        product = Item.objects.create(event=event, name='Ticket', default_price=10, admission=True)
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('2.00')
        event.settings.cancel_allow_user_paid_keep_fees = True
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True

        def create_paid_order(code):
            order = Order.objects.create(
                code=code,
                event=event,
                status=Order.STATUS_PAID,
                locale='en',
                datetime=now(),
                expires=now() + timedelta(days=10),
                total=Decimal('20.00'),
            )
            first = OrderPosition.objects.create(
                order=order,
                product=product,
                price=Decimal('10.00'),
                positionid=1,
            )
            second = OrderPosition.objects.create(
                order=order,
                product=product,
                price=Decimal('10.00'),
                positionid=2,
            )
            extra_fee_values = {
                OrderFee.FEE_TYPE_PAYMENT: Decimal('3.00'),
                OrderFee.FEE_TYPE_SHIPPING: Decimal('2.00'),
                OrderFee.FEE_TYPE_SERVICE: Decimal('1.00'),
            }
            extra_total = Decimal('0.00')
            for fee_type in fee_types:
                value = extra_fee_values[fee_type]
                order.fees.create(fee_type=fee_type, value=value)
                extra_total += value
            order.total += extra_total
            order.save(update_fields=['total'])
            order.payments.create(
                amount=order.total,
                state=OrderPayment.PAYMENT_STATE_CONFIRMED,
                provider='manual',
            )
            return order, first, second

        full_order, _first, _second = create_paid_order('KEEP-FULL')
        full_order = Order.objects.get(pk=full_order.pk)
        assert full_order.user_cancel_fee == expected_full_fee
        cancel_order(
            full_order.pk,
            cancellation_fee=full_order.user_cancel_fee,
            cancel_invoice=False,
        )
        full_order.refresh_from_db()

        staged_order, staged_first, _staged_second = create_paid_order('KEEP-STAGED')
        staged_order = Order.objects.get(pk=staged_order.pk)
        _cancel_order_positions(staged_order.pk, [staged_first.pk])
        staged_order = Order.objects.get(pk=staged_order.pk)
        assert staged_order.user_cancel_fee == expected_full_fee
        cancel_order(
            staged_order.pk,
            cancellation_fee=staged_order.user_cancel_fee,
            cancel_invoice=False,
        )
        staged_order = Order.objects.get(pk=staged_order.pk)
        full_order = Order.objects.get(pk=full_order.pk)

        assert full_order.user_existing_cancellation_fee == expected_full_fee
        assert staged_order.user_existing_cancellation_fee == expected_full_fee
        assert full_order.pending_sum == staged_order.pending_sum


@pytest.mark.django_db
def test_fixed_fee_above_single_ticket_value_matches_direct_cancellation(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('0.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('15.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        direct_order, _direct_positions = create_paid_cancellation_order(
            event,
            'FIXED-DIRECT',
            [Decimal('5.00'), Decimal('5.00')],
            ((OrderFee.FEE_TYPE_OTHER, Decimal('10.00')),),
        )
        staged_order, staged_positions = create_paid_cancellation_order(
            event,
            'FIXED-STAGED',
            [Decimal('5.00'), Decimal('5.00')],
            ((OrderFee.FEE_TYPE_OTHER, Decimal('10.00')),),
        )
        direct_order = Order.objects.get(pk=direct_order.pk)
        staged_order = Order.objects.get(pk=staged_order.pk)

        assert direct_order.user_cancel_fee == Decimal('15.00')
        _cancel_order_positions(staged_order.pk, [staged_positions[0].pk])
        staged_order.refresh_from_db()
        assert staged_order.user_cancel_fee == Decimal('15.00')

        cancel_order(
            direct_order.pk,
            cancellation_fee=direct_order.user_cancel_fee,
            cancel_invoice=False,
        )
        cancel_order(
            staged_order.pk,
            cancellation_fee=staged_order.user_cancel_fee,
            cancel_invoice=False,
        )
        direct_order = Order.objects.get(pk=direct_order.pk)
        staged_order = Order.objects.get(pk=staged_order.pk)

        assert direct_order.user_existing_cancellation_fee == Decimal('15.00')
        assert staged_order.user_existing_cancellation_fee == Decimal('15.00')
        assert direct_order.pending_sum == staged_order.pending_sum == Decimal('-5.00')

        insufficient_order, _positions = create_paid_cancellation_order(
            event,
            'OVER-CREDIT',
            [Decimal('5.00'), Decimal('5.00')],
        )
        with pytest.raises(OrderError):
            cancel_order(
                insufficient_order.pk,
                cancellation_fee=Decimal('15.00'),
                cancel_invoice=False,
            )
        insufficient_order.refresh_from_db()
        assert insufficient_order.status == Order.STATUS_PAID
        assert insufficient_order.total == Decimal('10.00')
        assert insufficient_order.user_existing_cancellation_fee == Decimal('0.00')


@pytest.mark.django_db
def test_nonretained_fee_in_order_total_matches_direct_cancellation(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('2.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        fees = ((OrderFee.FEE_TYPE_OTHER, Decimal('4.00')),)
        direct_order, _direct_positions = create_paid_cancellation_order(
            event,
            'OTHER-FEE-DIRECT',
            [Decimal('10.00'), Decimal('10.00')],
            fees,
        )
        staged_order, staged_positions = create_paid_cancellation_order(
            event,
            'OTHER-FEE-STAGED',
            [Decimal('10.00'), Decimal('10.00')],
            fees,
        )
        direct_order = Order.objects.get(pk=direct_order.pk)
        staged_order = Order.objects.get(pk=staged_order.pk)

        assert direct_order.user_cancel_fee == Decimal('4.40')
        _cancel_order_positions(staged_order.pk, [staged_positions[0].pk])
        staged_order.refresh_from_db()
        assert staged_order.user_cancel_fee == Decimal('4.40')

        cancel_order(
            direct_order.pk,
            cancellation_fee=direct_order.user_cancel_fee,
            cancel_invoice=False,
        )
        cancel_order(
            staged_order.pk,
            cancellation_fee=staged_order.user_cancel_fee,
            cancel_invoice=False,
        )
        direct_order = Order.objects.get(pk=direct_order.pk)
        staged_order = Order.objects.get(pk=staged_order.pk)

        assert direct_order.user_existing_cancellation_fee == Decimal('4.40')
        assert staged_order.user_existing_cancellation_fee == Decimal('4.40')
        assert direct_order.pending_sum == staged_order.pending_sum == Decimal('-19.60')


@pytest.mark.django_db
def test_changed_cancellation_settings_invalidate_cumulative_metadata(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('0.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'CHANGED-SETTINGS',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('20.00')
        order = Order.objects.get(pk=order.pk)
        summary = order.customer_cancellation_summary()
        assert summary is not None
        assert summary[5]['percentage'] == '10.00'
        assert order.user_cancel_fee == Decimal('3.00')

        _cancel_order_positions(order.pk, [positions[1].pk])
        order = Order.objects.get(pk=order.pk)
        assert order.user_existing_cancellation_fee == Decimal('2.00')
        assert order.user_cancel_fee == Decimal('3.00')
        cancel_order(order.pk, cancellation_fee=order.user_cancel_fee, cancel_invoice=False)
        order = Order.objects.get(pk=order.pk)
        assert order.user_existing_cancellation_fee == Decimal('3.00')


@pytest.mark.django_db
def test_changed_ticket_price_invalidates_cumulative_metadata(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'CHANGED-PRICE',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        positions[1].price = Decimal('11.00')
        positions[1].save(update_fields=['price'])
        order.refresh_from_db()
        order.total += Decimal('1.00')
        order.save(update_fields=['total'])
        order = Order.objects.get(pk=order.pk)
        assert order.customer_cancellation_summary() is None


@pytest.mark.django_db
def test_changed_retained_fee_invalidates_cumulative_metadata(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep_fees = True
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'RETAIN-FEE',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
            ((OrderFee.FEE_TYPE_PAYMENT, Decimal('2.00')),),
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        retained_fee = order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        retained_fee.value = Decimal('3.00')
        retained_fee.save(update_fields=['value'])
        order = Order.objects.get(pk=order.pk)

        assert order.customer_cancellation_summary() is None


@pytest.mark.django_db
def test_reinstatement_after_customer_cancellation_invalidates_metadata(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'REINSTATED',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        order = Order.objects.get(pk=order.pk)
        position = order.all_positions.get(pk=positions[0].pk)
        manager = OrderChangeManager(order=order, notify=False, reissue_invoice=False)
        manager.reinstate(position)
        manager.commit()
        position.refresh_from_db()
        order.refresh_from_db()

        assert Order.CUSTOMER_CANCELLATION_META_KEY not in position.meta_info_data
        assert order.customer_cancellation_summary() is None


@pytest.mark.django_db
def test_replacement_after_customer_cancellation_clears_metadata(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'REPLACED',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        order = Order.objects.get(pk=order.pk)
        position = order.all_positions.get(pk=positions[0].pk)
        replacement = Item.objects.create(
            event=event,
            name='Replacement',
            default_price=Decimal('10.00'),
            admission=True,
        )
        quota = event.quotas.create(name='Replacement quota', size=None)
        quota.products.add(replacement)
        order = Order.objects.get(pk=order.pk)
        position = order.all_positions.get(pk=positions[0].pk)
        manager = OrderChangeManager(order=order, notify=False, reissue_invoice=False)
        manager.change_product(position, replacement, None)
        manager.commit()
        position.refresh_from_db()
        order.refresh_from_db()

        assert position.product == replacement
        assert Order.CUSTOMER_CANCELLATION_META_KEY not in position.meta_info_data
        assert order.customer_cancellation_summary() is None


@pytest.mark.django_db
def test_split_after_customer_cancellation_invalidates_metadata(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'SPLIT-CANCEL',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])

        order = Order.objects.get(pk=order.pk)
        manager = OrderChangeManager(order=order, notify=False, reissue_invoice=False)
        moved_position = order.all_positions.get(pk=positions[0].pk)
        assert Order.CUSTOMER_CANCELLATION_META_KEY in moved_position.meta_info_data
        manager.split(moved_position)
        manager.commit()
        order.refresh_from_db()
        moved_position.refresh_from_db()

        assert manager.split_order is not None
        assert Order.CUSTOMER_CANCELLATION_META_KEY not in moved_position.meta_info_data
        assert order.customer_cancellation_summary() is None


@pytest.mark.django_db
def test_existing_refund_then_another_cancellation_keeps_refund_due_correct(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'REFUND-CANCEL',
            [Decimal('10.00'), Decimal('10.00'), Decimal('10.00')],
        )
        _cancel_order_positions(order.pk, [positions[0].pk])
        order.refresh_from_db()
        order.refunds.create(
            source=OrderRefund.REFUND_SOURCE_BUYER,
            state=OrderRefund.REFUND_STATE_DONE,
            amount=Decimal('9.00'),
            provider='manual',
            execution_date=now(),
        )
        order.refresh_from_db()
        assert order.pending_sum == Decimal('0.00')

        _cancel_order_positions(order.pk, [positions[1].pk])
        order.refresh_from_db()
        assert order.pending_sum == Decimal('-9.00')

        cancellation_fee = order.user_cancel_fee
        cancel_order(
            order.pk,
            cancellation_fee=cancellation_fee,
            cancel_invoice=False,
        )
        order = Order.objects.get(pk=order.pk)

        assert order.user_existing_cancellation_fee == Decimal('3.00')
        assert order.pending_sum == Decimal('-18.00')
        assert order.refunds.count() == 1


@pytest.mark.django_db
def test_multiple_successive_partial_cancellations_use_cumulative_fee(event):
    with scope(organizer=event.organizer, event=event):
        product = Item.objects.create(event=event, name='Ticket', default_price=10, admission=True)
        order = Order.objects.create(
            code='SUCCESSIVE',
            event=event,
            status=Order.STATUS_PAID,
            locale='en',
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('30.00'),
        )
        positions = [
            OrderPosition.objects.create(
                order=order,
                product=product,
                price=Decimal('10.00'),
                positionid=index,
            )
            for index in range(1, 4)
        ]
        order.payments.create(
            amount=Decimal('30.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='manual',
        )
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10')
        event.settings.cancel_allow_user_paid_keep = Decimal('2.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order = Order.objects.get(pk=order.pk)

        _cancel_order_positions(order.pk, [positions[0].pk])
        order.refresh_from_db()
        assert order.user_existing_cancellation_fee == Decimal('1.67')
        assert order.user_partial_cancel_fee(Decimal('10.00')) == Decimal('1.66')

        _cancel_order_positions(order.pk, [positions[1].pk])
        order.refresh_from_db()
        order = Order.objects.get(pk=order.pk)
        assert order.user_existing_cancellation_fee == Decimal('3.33')
        assert order.user_cancel_fee == Decimal('5.00')


@pytest.mark.django_db
def test_cancellation_order_permutations_match_direct_full_cancellation(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('2.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        direct_order, _ = create_paid_cancellation_order(
            event,
            'ORDER-DIRECT',
            [Decimal('10.00')] * 3,
        )
        ab_order, ab_positions = create_paid_cancellation_order(
            event,
            'ORDER-AB',
            [Decimal('10.00')] * 3,
        )
        ba_order, ba_positions = create_paid_cancellation_order(
            event,
            'ORDER-BA',
            [Decimal('10.00')] * 3,
        )

        direct_order = Order.objects.get(pk=direct_order.pk)
        direct_fee = direct_order.user_cancel_fee
        cancel_order(direct_order.pk, cancellation_fee=direct_fee, cancel_invoice=False)
        direct_order.refresh_from_db()

        for order, positions, indices in (
            (ab_order, ab_positions, (0, 1)),
            (ba_order, ba_positions, (1, 0)),
        ):
            _cancel_order_positions(order.pk, [positions[indices[0]].pk])
            _cancel_order_positions(order.pk, [positions[indices[1]].pk])
            order = Order.objects.get(pk=order.pk)
            staged_fee = order.user_cancel_fee
            cancel_order(order.pk, cancellation_fee=staged_fee, cancel_invoice=False)
            order = Order.objects.get(pk=order.pk)

            assert order.user_existing_cancellation_fee == direct_fee
            assert order.pending_sum == direct_order.pending_sum


@pytest.mark.django_db
def test_unequal_ticket_cancellation_orders_match_direct_fee(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('5.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        prices = [Decimal('5.00'), Decimal('20.00'), Decimal('50.00')]
        direct_order, _ = create_paid_cancellation_order(event, 'UNEQUAL-DIRECT', prices)
        ab_order, ab_positions = create_paid_cancellation_order(event, 'UNEQUAL-AB', prices)
        ca_order, ca_positions = create_paid_cancellation_order(event, 'UNEQUAL-CA', prices)

        direct_order = Order.objects.get(pk=direct_order.pk)
        direct_fee = direct_order.user_cancel_fee
        cancel_order(direct_order.pk, cancellation_fee=direct_fee, cancel_invoice=False)
        direct_order.refresh_from_db()

        _cancel_order_positions(ab_order.pk, [ab_positions[0].pk])
        ab_order = Order.objects.get(pk=ab_order.pk)
        assert ab_order.user_existing_cancellation_fee == Decimal('0.83')
        _cancel_order_positions(ab_order.pk, [ab_positions[1].pk])
        ab_order = Order.objects.get(pk=ab_order.pk)
        assert ab_order.user_existing_cancellation_fee == Decimal('4.17')
        cancel_order(ab_order.pk, cancellation_fee=ab_order.user_cancel_fee, cancel_invoice=False)
        ab_order = Order.objects.get(pk=ab_order.pk)

        _cancel_order_positions(ca_order.pk, [ca_positions[2].pk])
        ca_order = Order.objects.get(pk=ca_order.pk)
        assert ca_order.user_existing_cancellation_fee == Decimal('8.33')
        _cancel_order_positions(ca_order.pk, [ca_positions[0].pk])
        ca_order = Order.objects.get(pk=ca_order.pk)
        assert ca_order.user_existing_cancellation_fee == Decimal('9.17')
        cancel_order(ca_order.pk, cancellation_fee=ca_order.user_cancel_fee, cancel_invoice=False)
        ca_order = Order.objects.get(pk=ca_order.pk)

        assert direct_fee == Decimal('12.50')
        for order in (ab_order, ca_order):
            assert order.user_existing_cancellation_fee == direct_fee
            assert order.pending_sum == direct_order.pending_sum
        assert direct_order.pending_sum == Decimal('-62.50')


_MISSING_METADATA = object()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'original_total',
    [
        pytest.param(_MISSING_METADATA, id='missing'),
        pytest.param('-1.00', id='negative'),
        pytest.param('not-a-decimal', id='invalid-string'),
        pytest.param('NaN', id='nan'),
        pytest.param('Infinity', id='infinity'),
        pytest.param('11.00', id='does-not-reconcile'),
    ],
)
def test_invalid_original_order_total_uses_legacy_fallback(event, original_total):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('2.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        order, positions = create_paid_cancellation_order(
            event,
            'BAD-ORIG-TOTAL',
            [Decimal('5.00'), Decimal('5.00')],
        )
        position = positions[0]
        position.canceled = True
        metadata = {
            'order_code': order.code,
            'ticket_value': '5.00',
            'fee_value': '0.00',
            'original_ticket_value': '10.00',
            'retained_extra_fees': '0.00',
            'settings': order.customer_cancellation_settings(),
        }
        if original_total is not _MISSING_METADATA:
            metadata['original_order_total'] = original_total
        position.meta_info = json.dumps({Order.CUSTOMER_CANCELLATION_META_KEY: metadata})
        position.save(update_fields=['canceled', 'meta_info'])
        order.total = Decimal('5.00')
        order.save(update_fields=['total'])

        order = Order.objects.get(pk=order.pk)
        assert order.customer_cancellation_summary() is None
        assert order.user_cancel_fee == Decimal('2.50')


@pytest.mark.django_db
def test_automatic_refunds_only_refund_new_cancellation_balance(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('0.00')
        event.settings.cancel_allow_user_paid_keep_fees = False
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        order, positions = create_paid_cancellation_order(
            event,
            'AUTO-REFUND',
            [Decimal('10.00')] * 3,
            provider='testdummy_partialrefund',
        )

        cancel_order_positions(order.pk, [positions[0].pk], try_auto_refund=True)
        order = Order.objects.get(pk=order.pk)
        refunds = list(order.refunds.order_by('local_id'))
        assert [refund.amount for refund in refunds] == [Decimal('9.00')]
        assert order.pending_sum == Decimal('0.00')

        cancel_order_positions(order.pk, [positions[1].pk], try_auto_refund=True)
        order = Order.objects.get(pk=order.pk)
        refunds = list(order.refunds.order_by('local_id'))
        assert [refund.amount for refund in refunds] == [Decimal('9.00'), Decimal('9.00')]
        assert sum((refund.amount for refund in refunds), Decimal('0.00')) == Decimal('18.00')
        assert order.pending_sum == Decimal('0.00')
        assert order.payments.get().refunded_amount == Decimal('18.00')

        cancel_order(
            order.pk,
            cancellation_fee=order.user_cancel_fee,
            try_auto_refund=True,
            cancel_invoice=False,
        )
        order = Order.objects.get(pk=order.pk)
        refunds = list(order.refunds.order_by('local_id'))
        assert [refund.amount for refund in refunds] == [Decimal('9.00')] * 3
        assert order.user_existing_cancellation_fee == Decimal('3.00')
        assert order.pending_sum == Decimal('0.00')
        assert order.payments.get().refunded_amount == Decimal('27.00')


@pytest.mark.django_db
def test_intermediate_retained_fee_allocation_uses_ticket_value(event):
    with scope(organizer=event.organizer, event=event):
        event.settings.cancel_allow_user_paid_keep_percentage = Decimal('10.00')
        event.settings.cancel_allow_user_paid_keep = Decimal('3.00')
        event.settings.cancel_allow_user_paid_keep_fees = True
        event.settings.allow_modifications = 'order'
        event.settings.cancel_allow_user_paid = True
        prices = [Decimal('5.00'), Decimal('20.00'), Decimal('50.00')]
        retained_fees = (
            (OrderFee.FEE_TYPE_PAYMENT, Decimal('3.00')),
            (OrderFee.FEE_TYPE_SHIPPING, Decimal('2.00')),
            (OrderFee.FEE_TYPE_SERVICE, Decimal('1.00')),
        )
        direct_order, _ = create_paid_cancellation_order(
            event,
            'RETAINED-DIRECT',
            prices,
            retained_fees,
        )
        staged_order, positions = create_paid_cancellation_order(
            event,
            'RETAINED-STAGED',
            prices,
            retained_fees,
        )

        direct_order = Order.objects.get(pk=direct_order.pk)
        direct_fee = direct_order.user_cancel_fee
        assert direct_fee == Decimal('16.50')
        cancel_order(direct_order.pk, cancellation_fee=direct_fee, cancel_invoice=False)
        direct_order.refresh_from_db()

        _cancel_order_positions(staged_order.pk, [positions[0].pk])
        staged_order = Order.objects.get(pk=staged_order.pk)
        assert staged_order.user_existing_cancellation_fee == Decimal('1.10')

        _cancel_order_positions(staged_order.pk, [positions[1].pk])
        staged_order = Order.objects.get(pk=staged_order.pk)
        assert staged_order.user_existing_cancellation_fee == Decimal('5.50')
        assert staged_order.user_cancel_fee == direct_fee

        cancel_order(
            staged_order.pk,
            cancellation_fee=staged_order.user_cancel_fee,
            cancel_invoice=False,
        )
        staged_order = Order.objects.get(pk=staged_order.pk)
        assert staged_order.user_existing_cancellation_fee == direct_fee
        assert staged_order.pending_sum == direct_order.pending_sum == Decimal('-64.50')


@pytest.fixture
def clist_autocheckin(event):
    c = event.checkin_lists.create(name='Default', all_products=True, auto_checkin_sales_channels=['web'])
    return c


@pytest.mark.django_db
def test_expiry_days(event):
    today = now()
    event.settings.set('payment_term_days', 5)
    event.settings.set('payment_term_weekdays', False)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 5


@pytest.mark.django_db
def test_expiry_weekdays(event):
    today = make_aware(datetime(2016, 9, 20, 15, 0, 0, 0))
    event.settings.set('payment_term_days', 5)
    event.settings.set('payment_term_weekdays', True)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 6
    assert order.expires.weekday() == 0

    today = make_aware(datetime(2016, 9, 19, 15, 0, 0, 0))
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 7
    assert order.expires.weekday() == 0


@pytest.mark.django_db
def test_expiry_minutes(event):
    today = now()
    event.settings.set('payment_term_days', 5)
    event.settings.set('payment_term_mode', 'minutes')
    event.settings.set('payment_term_minutes', 30)
    event.settings.set('payment_term_weekdays', False)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 0
    assert (order.expires - today).seconds == 30 * 60


@pytest.mark.django_db
def test_expiry_last(event):
    today = now()
    event.settings.set('payment_term_days', 5)
    event.settings.set('payment_term_weekdays', False)
    event.settings.set('payment_term_last', now() + timedelta(days=3))
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 3
    event.settings.set('payment_term_last', now() + timedelta(days=7))
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 5


@pytest.mark.django_db
def test_expiry_last_relative(event):
    today = now()
    event.settings.set('payment_term_days', 5)
    event.settings.set('payment_term_weekdays', False)
    event.date_from = now() + timedelta(days=5)
    event.save()
    event.settings.set(
        'payment_term_last',
        RelativeDateWrapper(
            RelativeDate(
                days_before=2,
                time=None,
                base_date_name='date_from',
                minutes_before=None,
            )
        ),
    )
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 3


@pytest.mark.django_db
def test_expiry_last_relative_subevents(event):
    today = now()
    event.settings.set('payment_term_days', 100)
    event.settings.set('payment_term_weekdays', False)
    event.date_from = now() + timedelta(days=5)
    event.has_subevents = True
    event.save()
    tr7 = event.tax_rules.create(rate=Decimal('17.00'))
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        tax_rule=tr7,
        default_price=Decimal('23.00'),
        admission=True,
    )

    se1 = event.subevents.create(name='SE1', date_from=now() + timedelta(days=10))
    se2 = event.subevents.create(name='SE2', date_from=now() + timedelta(days=8))

    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        subevent=se1,
        event=event,
        cart_id='123',
    )
    cp2 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        subevent=se2,
        event=event,
        cart_id='123',
    )

    event.settings.set(
        'payment_term_last',
        RelativeDateWrapper(
            RelativeDate(
                days_before=2,
                time=None,
                base_date_name='date_from',
                minutes_before=None,
            )
        ),
    )
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1, cp2],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert (order.expires - today).days == 6


@pytest.mark.django_db
def test_expiry_dst(event):
    event.settings.set('timezone', 'Europe/Berlin')
    tz = ZoneInfo('Europe/Berlin')
    utc = ZoneInfo('UTC')
    today = datetime(2016, 10, 29, 12, 0, 0, tzinfo=tz).astimezone(utc)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    localex = order.expires.astimezone(tz)
    assert (localex.hour, localex.minute) == (23, 59)


@pytest.mark.django_db
def test_expiring(event):
    o1 = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        locale='en',
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=0,
    )
    o2 = Order.objects.create(
        code='FO2',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        locale='en',
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=12,
    )
    generate_invoice(o2)
    expire_orders(None)
    o1 = Order.objects.get(id=o1.id)
    assert o1.status == Order.STATUS_PENDING
    o2 = Order.objects.get(id=o2.id)
    assert o2.status == Order.STATUS_EXPIRED
    assert o2.invoices.count() == 2
    assert o2.invoices.last().is_cancellation is True


@pytest.mark.django_db
def test_expiring_paid_invoice(event):
    o2 = Order.objects.create(
        code='FO2',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        locale='en',
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=12,
    )
    generate_invoice(o2)
    expire_orders(None)
    o2 = Order.objects.get(id=o2.id)
    assert o2.status == Order.STATUS_EXPIRED
    assert o2.invoices.count() == 2
    o2.payments.create(provider='manual', amount=o2.total).confirm()
    assert o2.invoices.count() == 3
    assert o2.invoices.last().is_cancellation is False


@pytest.mark.django_db
def test_create_external_refund_exact_balance_marks_refund_done(event):
    order = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PAID,
        locale='en',
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=Decimal('100.00'),
    )
    payment = order.payments.create(
        provider='banktransfer',
        state=OrderPayment.PAYMENT_STATE_CONFIRMED,
        amount=Decimal('120.00'),
    )
    assert order.pending_sum == Decimal('-20.00')

    refund = payment.create_external_refund(amount=Decimal('20.00'))

    refund.refresh_from_db()
    assert refund.state == OrderRefund.REFUND_STATE_DONE
    order.refresh_from_db()
    assert order.pending_sum == Decimal('0.00')
    payment.refresh_from_db()
    assert payment.state == OrderPayment.PAYMENT_STATE_CONFIRMED


@pytest.mark.django_db
def test_expire_twice(event):
    o2 = Order.objects.create(
        code='FO2',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        locale='en',
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=12,
    )
    generate_invoice(o2)
    expire_orders(None)
    o2 = Order.objects.get(id=o2.id)
    assert o2.status == Order.STATUS_EXPIRED
    assert o2.invoices.count() == 2
    # this would usually happen when the deadline is extended, but lets keep the case simple
    o2.status = Order.STATUS_PENDING
    o2.save()
    expire_orders(None)
    o2 = Order.objects.get(id=o2.id)
    assert o2.status == Order.STATUS_EXPIRED
    assert o2.invoices.count() == 2


@pytest.mark.django_db
def test_expiring_auto_disabled(event):
    event.settings.set('payment_term_expire_automatically', False)
    o1 = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=0,
    )
    o2 = Order.objects.create(
        code='FO2',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=0,
    )
    expire_orders(None)
    o1 = Order.objects.get(id=o1.id)
    assert o1.status == Order.STATUS_PENDING
    o2 = Order.objects.get(id=o2.id)
    assert o2.status == Order.STATUS_PENDING


@pytest.mark.django_db
def test_do_not_expire_if_approval_pending(event):
    o1 = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=0,
        require_approval=True,
    )
    o2 = Order.objects.create(
        code='FO2',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=0,
    )
    expire_orders(None)
    o1 = Order.objects.get(id=o1.id)
    assert o1.status == Order.STATUS_PENDING
    o2 = Order.objects.get(id=o2.id)
    assert o2.status == Order.STATUS_EXPIRED


@pytest.mark.django_db
def test_approve(event):
    djmail.outbox = []
    event.settings.invoice_generate = 'True'
    o1 = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=10,
        require_approval=True,
        locale='en',
    )
    approve_order(o1)
    o1.refresh_from_db()
    assert o1.expires > now()
    assert o1.status == Order.STATUS_PENDING
    assert not o1.require_approval
    assert o1.invoices.count() == 1
    assert len(djmail.outbox) == 1
    assert 'awaiting payment' in djmail.outbox[0].subject


@pytest.mark.django_db
def test_approve_free(event):
    djmail.outbox = []
    event.settings.invoice_generate = 'True'
    o1 = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=0,
        require_approval=True,
    )
    approve_order(o1)
    o1.refresh_from_db()
    assert o1.expires > now()
    assert o1.status == Order.STATUS_PAID
    assert not o1.require_approval
    assert o1.invoices.count() == 0
    assert len(djmail.outbox) == 1
    assert 'confirmed' in djmail.outbox[0].subject


@pytest.mark.django_db
def test_approve_free_after_last_payment_date(event):
    event.settings.payment_term_last = (now() - timedelta(days=1)).date().isoformat()
    djmail.outbox = []
    event.settings.invoice_generate = 'True'
    o1 = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=0,
        require_approval=True,
    )
    approve_order(o1)
    o1.refresh_from_db()
    assert o1.status == Order.STATUS_PAID
    assert not o1.require_approval
    assert o1.invoices.count() == 0
    assert len(djmail.outbox) == 1
    assert 'confirmed' in djmail.outbox[0].subject


@pytest.mark.django_db
def test_deny(event):
    djmail.outbox = []
    event.settings.invoice_generate = 'True'
    o1 = Order.objects.create(
        code='FOO',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PENDING,
        datetime=now(),
        expires=now() - timedelta(days=10),
        total=10,
        require_approval=True,
        locale='en',
    )
    generate_invoice(o1)
    deny_order(o1)
    o1.refresh_from_db()
    assert o1.expires < now()
    assert o1.status == Order.STATUS_CANCELED
    assert o1.require_approval
    assert o1.invoices.count() == 2
    assert len(djmail.outbox) == 1
    assert 'denied' in djmail.outbox[0].subject


class PaymentReminderTests(TestCase):
    def setUp(self):
        super().setUp()
        self.o = Organizer.objects.create(name='Dummy', slug='dummy')
        with scope(organizer=self.o):
            self.event = Event.objects.create(
                organizer=self.o,
                name='Dummy',
                slug='dummy',
                date_from=now() + timedelta(days=2),
                plugins='eventyay.plugins.banktransfer',
            )
            self.order = Order.objects.create(
                code='FOO',
                event=self.event,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                locale='en',
                datetime=now() - timedelta(hours=4),
                expires=now().replace(hour=5, minute=0, second=0) + timedelta(days=10),
                total=Decimal('46.00'),
            )
            self.ticket = Item.objects.create(
                event=self.event,
                name='Early-bird ticket',
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.op1 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Peter'},
                positionid=1,
            )
            djmail.outbox = []

    @classscope(attr='o')
    def test_disabled(self):
        send_expiry_warnings(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    @pytest.mark.django_db
    def test_order_payment_term_check_accepts_event_timezone_name(self):
        self.event.timezone = 'Europe/Berlin'
        self.event.save()
        self.event.settings.set('payment_term_last', (now() - timedelta(days=1)).date().isoformat())

        with pytest.raises(OrderError):
            _check_date(self.event, now())


    def test_sent_once(self):
        self.event.settings.mail_days_order_expire_warning = 12
        send_expiry_warnings(sender=self.event)
        assert len(djmail.outbox) == 1

    @classscope(attr='o')
    def test_paid(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        send_expiry_warnings(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_sent_days(self):
        self.event.settings.mail_days_order_expire_warning = 9
        send_expiry_warnings(sender=self.event)
        assert len(djmail.outbox) == 0
        self.event.settings.mail_days_order_expire_warning = 10
        send_expiry_warnings(sender=self.event)
        assert len(djmail.outbox) == 1

    @classscope(attr='o')
    def test_sent_not_immediately_after_purchase(self):
        self.order.datetime = now()
        self.order.expires = now() + timedelta(hours=3)
        self.order.save()
        self.event.settings.mail_days_order_expire_warning = 2
        send_expiry_warnings(sender=self.event)
        assert len(djmail.outbox) == 0


class DownloadReminderTests(TestCase):
    def setUp(self):
        super().setUp()
        self.o = Organizer.objects.create(name='Dummy', slug='dummy')
        with scope(organizer=self.o):
            self.event = Event.objects.create(
                organizer=self.o,
                name='Dummy',
                slug='dummy',
                date_from=now() + timedelta(days=2),
                plugins='eventyay.plugins.banktransfer',
            )
            self.order = Order.objects.create(
                code='FOO',
                event=self.event,
                email='dummy@dummy.test',
                status=Order.STATUS_PAID,
                locale='en',
                datetime=now() - timedelta(days=4),
                expires=now() - timedelta(hours=4) + timedelta(days=10),
                total=Decimal('46.00'),
            )
            self.ticket = Item.objects.create(
                event=self.event,
                name='Early-bird ticket',
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.op1 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Peter'},
                positionid=1,
            )
            self.event.settings.ticket_download = True
            djmail.outbox = []

    @classscope(attr='o')
    def test_downloads_disabled(self):
        self.event.settings.mail_days_download_reminder = 2
        self.event.settings.ticket_download = False
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_downloads_disabled_per_product(self):
        self.event.settings.mail_days_download_reminder = 2
        self.ticket.generate_tickets = False
        self.ticket.save()
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_disabled(self):
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_sent_once(self):
        self.event.settings.mail_days_download_reminder = 2
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 1
        assert djmail.outbox[0].to == ['dummy@dummy.test']
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 1

    @classscope(attr='o')
    def test_send_to_attendees(self):
        self.event.settings.mail_send_download_reminder_attendee = True
        self.event.settings.mail_days_download_reminder = 2
        self.op1.attendee_email = 'attendee@dummy.test'
        self.op1.save()
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 2
        assert djmail.outbox[0].to == ['dummy@dummy.test']
        assert djmail.outbox[1].to == ['attendee@dummy.test']
        assert '/ticket/' in djmail.outbox[1].body
        assert '/order/' not in djmail.outbox[1].body

    @classscope(attr='o')
    def test_send_to_attendees_subevent_past(self):
        se1 = self.event.subevents.create(name='Foo', date_from=now() - timedelta(days=2))
        self.op1.subevent = se1
        self.op1.attendee_email = 'attendee@dummy.test'
        self.op1.save()
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_send_to_attendees_subevent_future(self):
        self.event.settings.mail_send_download_reminder_attendee = True
        self.event.settings.mail_days_download_reminder = 2
        se1 = self.event.subevents.create(name='Foo', date_from=now() + timedelta(days=2))
        se2 = self.event.subevents.create(name='Foo', date_from=now() + timedelta(days=8))
        self.op1.subevent = se1
        self.op1.attendee_email = 'attendee@dummy.test'
        self.op1.save()
        self.op2 = OrderPosition.objects.create(
            order=self.order,
            product=self.ticket,
            variation=None,
            subevent=se2,
            attendee_email='attendee2@dummy.test',
            price=Decimal('23.00'),
            attendee_name_parts={'full_name': 'Peter'},
            positionid=1,
        )
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 2
        assert djmail.outbox[0].to == ['dummy@dummy.test']
        assert djmail.outbox[1].to == ['attendee@dummy.test']

    @classscope(attr='o')
    def test_send_not_to_attendees_with_same_address(self):
        self.event.settings.mail_send_download_reminder_attendee = True
        self.event.settings.mail_days_download_reminder = 2
        self.op1.attendee_email = 'dummy@dummy.test'
        self.op1.save()
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 1
        assert djmail.outbox[0].to == ['dummy@dummy.test']
        assert '/order/' in djmail.outbox[0].body

    @classscope(attr='o')
    def test_sent_paid_only(self):
        self.event.settings.mail_days_download_reminder = 2
        self.order.status = Order.STATUS_PENDING
        self.order.save()
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_not_sent_too_early(self):
        self.event.settings.mail_days_download_reminder = 1
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_not_sent_too_soon_after_purchase(self):
        self.order.datetime = now()
        self.order.save()
        self.event.settings.mail_days_download_reminder = 2
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_not_sent_after_reminder_date(self):
        self.order.datetime = self.event.date_from - timedelta(days=1)
        self.order.save()
        self.event.settings.mail_days_download_reminder = 2
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_not_sent_for_disabled_sales_channel(self):
        self.event.settings.mail_days_download_reminder = 2
        self.event.settings.mail_sales_channel_download_reminder = []
        send_download_reminders(sender=self.event)
        assert len(djmail.outbox) == 0


class OrderCancelTests(TestCase):
    def setUp(self):
        super().setUp()
        self.o = Organizer.objects.create(name='Dummy', slug='dummy')
        with scope(organizer=self.o):
            self.event = Event.objects.create(
                organizer=self.o,
                name='Dummy',
                slug='dummy',
                date_from=now(),
                plugins='tests.tickets.testdummy',
            )
            self.order = Order.objects.create(
                code='FOO',
                event=self.event,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                locale='en',
                datetime=now(),
                expires=now() + timedelta(days=10),
                total=Decimal('46.00'),
            )
            self.ticket = Item.objects.create(
                event=self.event,
                name='Early-bird ticket',
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.op1 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Peter'},
                positionid=1,
            )
            self.op2 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Dieter'},
                positionid=2,
            )
            generate_invoice(self.order)
            djmail.outbox = []

    @classscope(attr='o')
    def test_cancel_canceled(self):
        self.order.status = Order.STATUS_CANCELED
        self.order.save()
        with pytest.raises(OrderError):
            cancel_order(self.order.pk)

    @classscope(attr='o')
    def test_cancel_send_mail(self):
        cancel_order(self.order.pk, send_mail=True)
        assert len(djmail.outbox) == 1

    @classscope(attr='o')
    def test_cancel_send_no_mail(self):
        cancel_order(self.order.pk, send_mail=False)
        assert len(djmail.outbox) == 0

    @classscope(attr='o')
    def test_cancel_unpaid(self):
        cancel_order(self.order.pk)
        self.order.refresh_from_db()
        assert self.order.cancellation_date
        assert self.order.status == Order.STATUS_CANCELED
        assert self.order.all_logentries().last().action_type == 'eventyay.event.order.canceled'
        assert self.order.invoices.count() == 2

    @classscope(attr='o')
    def test_cancel_unpaid_with_voucher(self):
        self.op1.voucher = self.event.vouchers.create(product=self.ticket, redeemed=1)
        self.op1.save()
        cancel_order(self.order.pk)
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_CANCELED
        assert self.order.all_logentries().last().action_type == 'eventyay.event.order.canceled'
        self.op1.voucher.refresh_from_db()
        assert self.op1.voucher.redeemed == 0
        assert self.order.invoices.count() == 2

    @classscope(attr='o')
    def test_cancel_paid(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        cancel_order(self.order.pk)
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_CANCELED
        assert self.order.all_logentries().last().action_type == 'eventyay.event.order.canceled'
        assert self.order.invoices.count() == 2

    @classscope(attr='o')
    def test_cancel_paid_with_too_high_fee(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(state=OrderPayment.PAYMENT_STATE_CONFIRMED, amount=48.5)
        with pytest.raises(OrderError):
            cancel_order(self.order.pk, cancellation_fee=50)
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_PAID
        assert self.order.total == 46

    @classscope(attr='o')
    def test_cancel_paid_with_fee(self):
        f = self.order.fees.create(fee_type=OrderFee.FEE_TYPE_SHIPPING, value=2.5)
        self.order.status = Order.STATUS_PAID
        self.order.total = 48.5
        self.order.save()
        self.order.payments.create(state=OrderPayment.PAYMENT_STATE_CONFIRMED, amount=48.5)
        self.op1.voucher = self.event.vouchers.create(product=self.ticket, redeemed=1)
        self.op1.save()
        cancel_order(self.order.pk, cancellation_fee=2.5)
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_PAID
        self.op1.refresh_from_db()
        assert self.op1.canceled
        self.op2.refresh_from_db()
        assert self.op2.canceled
        f.refresh_from_db()
        assert f.canceled
        assert self.order.total == 2.5
        assert self.order.all_logentries().last().action_type == 'eventyay.event.order.canceled'
        self.op1.voucher.refresh_from_db()
        assert self.op1.voucher.redeemed == 0
        assert self.order.invoices.count() == 3
        assert not self.order.invoices.last().is_cancellation

    @classscope(attr='o')
    def test_cancel_paid_with_fee_change_secret(self):
        self.event.settings.ticket_secret_generator = 'pretix_sig1'
        s = self.op1.secret
        self.order.fees.create(fee_type=OrderFee.FEE_TYPE_SHIPPING, value=2.5)
        self.order.status = Order.STATUS_PAID
        self.order.total = 48.5
        self.order.save()
        self.order.payments.create(state=OrderPayment.PAYMENT_STATE_CONFIRMED, amount=48.5)
        self.op1.voucher = self.event.vouchers.create(product=self.ticket, redeemed=1)
        self.op1.save()
        cancel_order(self.order.pk, cancellation_fee=2.5)
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_PAID
        self.op1.refresh_from_db()
        assert self.op1.canceled
        assert self.op1.secret != s

    @classscope(attr='o')
    def test_auto_refund_possible(self):
        p1 = self.order.payments.create(
            amount=Decimal('46.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='testdummy_partialrefund',
        )
        cancel_order(self.order.pk, cancellation_fee=2, try_auto_refund=True)
        r = self.order.refunds.get()
        assert r.state == OrderRefund.REFUND_STATE_DONE
        assert r.amount == Decimal('44.00')
        assert r.source == OrderRefund.REFUND_SOURCE_BUYER
        assert r.payment == p1
        assert self.order.all_logentries().filter(action_type='eventyay.event.order.refund.created').exists()
        assert not self.order.all_logentries().filter(action_type='eventyay.event.order.refund.requested').exists()

    @classscope(attr='o')
    def test_auto_refund_possible_giftcard(self):
        gc = self.o.issued_gift_cards.create(currency='EUR')
        p1 = self.order.payments.create(
            amount=Decimal('46.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='giftcard',
            info='{"gift_card": %d}' % gc.pk,
        )
        cancel_order(self.order.pk, cancellation_fee=2, try_auto_refund=True)
        r = self.order.refunds.get()
        assert r.state == OrderRefund.REFUND_STATE_DONE
        assert r.amount == Decimal('44.00')
        assert r.source == OrderRefund.REFUND_SOURCE_BUYER
        assert r.payment == p1
        assert self.order.all_logentries().filter(action_type='eventyay.event.order.refund.created').exists()
        assert not self.order.all_logentries().filter(action_type='eventyay.event.order.refund.requested').exists()
        assert gc.value == Decimal('44.00')

    @classscope(attr='o')
    def test_auto_refund_possible_issued_giftcard(self):
        gc = self.o.issued_gift_cards.create(currency='EUR', issued_in=self.op1)
        gc.transactions.create(value=23)
        self.order.payments.create(
            amount=Decimal('46.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='testdummy_partialrefund',
        )
        cancel_order(self.order.pk, cancellation_fee=2, try_auto_refund=True)
        r = self.order.refunds.get()
        assert r.state == OrderRefund.REFUND_STATE_DONE
        assert gc.value == Decimal('0.00')

    @classscope(attr='o')
    def test_auto_refund_impossible_issued_giftcard_used(self):
        gc = self.o.issued_gift_cards.create(currency='EUR', issued_in=self.op1)
        gc.transactions.create(value=20)
        self.order.payments.create(
            amount=Decimal('46.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='testdummy_partialrefund',
        )
        with pytest.raises(OrderError):
            cancel_order(self.order.pk, cancellation_fee=2, try_auto_refund=True)
        assert gc.value == Decimal('20.00')

    @classscope(attr='o')
    def test_auto_refund_impossible(self):
        self.order.payments.create(
            amount=Decimal('46.00'),
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='testdummy_fullrefund',
        )
        cancel_order(self.order.pk, cancellation_fee=2, try_auto_refund=True)
        assert not self.order.refunds.exists()
        assert self.order.all_logentries().filter(action_type='eventyay.event.order.refund.requested').exists()


class OrderChangeManagerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.o = Organizer.objects.create(name='Dummy', slug='dummy')
        with scope(organizer=self.o):
            self.event = Event.objects.create(
                organizer=self.o,
                name='Dummy',
                slug='dummy',
                date_from=now(),
                plugins='eventyay.plugins.banktransfer',
            )
            self.order = Order.objects.create(
                code='FOO',
                event=self.event,
                email='dummy@dummy.test',
                status=Order.STATUS_PENDING,
                locale='en',
                datetime=now(),
                expires=now() + timedelta(days=10),
                total=Decimal('46.00'),
            )
            self.order.payments.create(
                provider='banktransfer',
                state=OrderPayment.PAYMENT_STATE_CREATED,
                amount=self.order.total,
            )
            self.tr7 = self.event.tax_rules.create(rate=Decimal('7.00'))
            self.tr19 = self.event.tax_rules.create(rate=Decimal('19.00'))
            self.ticket = Item.objects.create(
                event=self.event,
                name='Early-bird ticket',
                tax_rule=self.tr7,
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.ticket2 = Item.objects.create(
                event=self.event,
                name='Other ticket',
                tax_rule=self.tr7,
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.shirt = Item.objects.create(
                event=self.event,
                name='T-Shirt',
                tax_rule=self.tr19,
                default_price=Decimal('12.00'),
            )
            self.op1 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Peter'},
                positionid=1,
            )
            self.op2 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Dieter'},
                positionid=2,
            )
            self.ocm = OrderChangeManager(self.order, None)
            self.quota = self.event.quotas.create(name='Test', size=None)
            self.quota.products.add(self.ticket)
            self.quota.products.add(self.ticket2)
            self.quota.products.add(self.shirt)

            self.stalls = Item.objects.create(
                event=self.event,
                name='Stalls',
                tax_rule=self.tr7,
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.plan = SeatingPlan.objects.create(name='Plan', organizer=self.o, layout='{}')
            self.event.seat_category_mappings.create(layout_category='Stalls', product=self.stalls)
            self.quota.products.add(self.stalls)
            self.seat_a1 = self.event.seats.create(seat_number='A1', product=self.stalls, seat_guid='A1')
            self.seat_a2 = self.event.seats.create(seat_number='A2', product=self.stalls, seat_guid='A2')
            self.seat_a3 = self.event.seats.create(seat_number='A3', product=self.stalls, seat_guid='A3')

    def _enable_reverse_charge(self):
        self.tr7.eu_reverse_charge = True
        self.tr7.home_country = Country('DE')
        self.tr7.save()
        self.tr19.eu_reverse_charge = True
        self.tr19.home_country = Country('DE')
        self.tr19.save()
        return InvoiceAddress.objects.create(
            order=self.order,
            is_business=True,
            vat_id='ATU1234567',
            vat_id_validated=True,
            country=Country('AT'),
        )

    @classscope(attr='o')
    def test_multiple_commits_forbidden(self):
        self.ocm.change_price(self.op1, Decimal('10.00'))
        self.ocm.commit()
        self.ocm.change_price(self.op1, Decimal('42.00'))
        with self.assertRaises(OrderError):
            self.ocm.commit()

    @classscope(attr='o')
    def test_change_subevent_quota_required(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        self.op1.subevent = se1
        self.op1.save()
        self.quota.subevent = se1
        self.quota.save()
        with self.assertRaises(OrderError):
            self.ocm.change_subevent(self.op1, se2)

    @classscope(attr='o')
    def test_change_subevent_and_product(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        self.op1.subevent = se1
        self.op1.save()
        self.quota.subevent = se1
        self.quota.save()
        self.quota.products.remove(self.shirt)
        q2 = self.event.quotas.create(name='Q2', size=None, subevent=se2)
        q2.products.add(self.shirt)
        self.ocm.change_product_and_subevent(self.op1, self.shirt, None, se2)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.subevent == se2
        assert self.op1.product == self.shirt

    @classscope(attr='o')
    def test_change_subevent_success(self):
        self.event.has_subevents = True
        self.event.save()
        s = self.op1.secret
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        SubEventItem.objects.create(subevent=se2, product=self.ticket, price=12)
        self.op1.subevent = se1
        self.op1.save()
        self.quota.subevent = se2
        self.quota.save()

        self.ocm.change_subevent(self.op1, se2)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.subevent == se2
        assert self.op1.price == Decimal('23.00')
        assert self.order.total == self.op1.price + self.op2.price
        assert self.op1.secret == s

    @classscope(attr='o')
    def test_change_subevent_success_change_secret(self):
        self.event.settings.ticket_secret_generator = 'pretix_sig1'
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        SubEventItem.objects.create(subevent=se2, product=self.ticket, price=12)
        s = self.op1.secret
        self.op1.subevent = se1
        self.op1.save()
        self.quota.subevent = se2
        self.quota.save()

        self.ocm.change_subevent(self.op1, se2)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.subevent == se2
        assert self.op1.price == Decimal('23.00')
        assert self.order.total == self.op1.price + self.op2.price
        assert self.op1.secret != s

    @classscope(attr='o')
    def test_change_subevent_with_price_success(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        SubEventItem.objects.create(subevent=se2, product=self.ticket, price=12)
        self.op1.subevent = se1
        self.op1.save()
        self.quota.subevent = se2
        self.quota.save()

        self.ocm.change_subevent(self.op1, se2)
        self.ocm.change_price(self.op1, Decimal('12.00'))
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.subevent == se2
        assert self.op1.price == Decimal('12.00')
        assert self.order.total == self.op1.price + self.op2.price

    @classscope(attr='o')
    def test_change_subevent_sold_out(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        self.op1.subevent = se1
        self.op1.save()
        self.quota.subevent = se2
        self.quota.size = 0
        self.quota.save()

        self.ocm.change_subevent(self.op1, se2)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.subevent == se1

    @classscope(attr='o')
    def test_change_product_quota_required(self):
        self.quota.delete()
        with self.assertRaises(OrderError):
            self.ocm.change_product(self.op1, self.shirt, None)

    @classscope(attr='o')
    def test_change_new_secret_by_scheme(self):
        self.event.settings.ticket_secret_generator = 'pretix_sig1'
        s = self.op1.secret
        p = self.op1.price
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.shirt
        assert self.op1.price == p
        assert self.op1.tax_value == Decimal('3.67')
        assert self.op1.tax_rule == self.shirt.tax_rule
        assert self.op1.secret != s

    @classscope(attr='o')
    def test_change_product_keep_price(self):
        p = self.op1.price
        s = self.op1.secret
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.shirt
        assert self.op1.price == p
        assert self.op1.tax_value == Decimal('3.67')
        assert self.op1.tax_rule == self.shirt.tax_rule
        assert self.op1.secret == s

    @classscope(attr='o')
    def test_change_product_change_price_before_voucher(self):
        self.op1.voucher = self.event.vouchers.create(product=self.shirt, redeemed=1, price_mode='set', value='5.00')
        self.op1.price = Decimal('5.00')
        self.op1.price_before_voucher = Decimal('23.00')
        self.op1.save()
        p = self.op1.price
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.shirt
        assert self.op1.price == p
        assert self.op1.price_before_voucher == Decimal('12.00')

    @classscope(attr='o')
    def test_change_product_change_price_before_voucher_minimum_value(self):
        self.op1.voucher = self.event.vouchers.create(product=self.shirt, redeemed=1, price_mode='set', value='20.00')
        self.op1.price = Decimal('20.00')
        self.op1.price_before_voucher = Decimal('23.00')
        self.op1.save()
        p = self.op1.price
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.shirt
        assert self.op1.price == p
        assert self.op1.price_before_voucher == Decimal('20.00')

    @classscope(attr='o')
    def test_change_product_success(self):
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.shirt
        assert self.op1.price == Decimal('23.00')
        assert self.op1.tax_rate == self.shirt.tax_rule.rate
        assert round_decimal(self.op1.price * (1 - 100 / (100 + self.op1.tax_rate))) == self.op1.tax_value
        assert self.order.total == self.op1.price + self.op2.price

    @classscope(attr='o')
    def test_change_product_with_price_success(self):
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.change_price(self.op1, Decimal('12.00'))
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.shirt
        assert self.op1.price == Decimal('12.00')
        assert self.op1.tax_rate == self.shirt.tax_rule.rate
        assert round_decimal(self.op1.price * (1 - 100 / (100 + self.op1.tax_rate))) == self.op1.tax_value
        assert self.order.total == self.op1.price + self.op2.price

    @classscope(attr='o')
    def test_change_price_success(self):
        self.ocm.change_price(self.op1, Decimal('24.00'))
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.ticket
        assert self.op1.price == Decimal('24.00')
        assert round_decimal(self.op1.price * (1 - 100 / (100 + self.op1.tax_rate))) == self.op1.tax_value
        assert self.order.total == self.op1.price + self.op2.price

    @classscope(attr='o')
    def test_change_price_net_success(self):
        self.tr7.price_includes_tax = False
        self.tr7.save()
        self.ocm.change_price(self.op1, Decimal('10.70'))
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.product == self.ticket
        assert self.op1.price == Decimal('10.70')
        assert round_decimal(self.op1.price * (1 - 100 / (100 + self.op1.tax_rate))) == self.op1.tax_value
        assert self.order.total == self.op1.price + self.op2.price

    @classscope(attr='o')
    def test_cancel_success(self):
        s = self.op1.secret
        self.ocm.cancel(self.op1)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 1
        assert self.order.total == self.op2.price
        self.op1.refresh_from_db()
        assert self.op1.canceled
        assert self.op1.secret == s

    @classscope(attr='o')
    def test_cancel_success_changed_secret(self):
        self.event.settings.ticket_secret_generator = 'pretix_sig1'
        s = self.op1.secret
        self.ocm.cancel(self.op1)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 1
        assert self.order.total == self.op2.price
        self.op1.refresh_from_db()
        assert self.op1.canceled
        assert self.op1.secret != s

    @classscope(attr='o')
    def test_cancel_with_addon(self):
        self.shirt.category = self.event.categories.create(name='Add-ons', is_addon=True)
        self.ticket.addons.create(addon_category=self.shirt.category)
        self.ocm.add_position(self.shirt, None, Decimal('13.00'), self.op1)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.ocm = OrderChangeManager(self.order, None)
        assert self.order.positions.count() == 3

        self.ocm.cancel(self.op1)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 1
        assert self.order.total == self.op2.price
        self.op1.refresh_from_db()
        assert self.op1.canceled
        assert self.op1.addons.first().canceled

    @classscope(attr='o')
    def test_free_to_paid(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.op1.price = Decimal('0.00')
        self.op1.save()
        self.op2.delete()
        self.order.total = Decimal('0.00')
        self.order.save()
        self.ocm.change_price(self.op1, Decimal('24.00'))
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.order.refresh_from_db()
        assert self.op1.price == Decimal('24.00')
        assert self.order.status == Order.STATUS_PENDING

    @classscope(attr='o')
    def test_cancel_issued_giftcard(self):
        gc = self.o.issued_gift_cards.create(currency='EUR', issued_in=self.op1)
        gc.transactions.create(value=23)
        self.ocm.cancel(self.op1)
        self.ocm.commit()
        assert gc.value == Decimal('0.00')

    @classscope(attr='o')
    def test_cancel_issued_giftcard_used(self):
        gc = self.o.issued_gift_cards.create(currency='EUR', issued_in=self.op1)
        gc.transactions.create(value=20)
        self.ocm.cancel(self.op1)
        with self.assertRaises(OrderError):
            self.ocm.commit()

    @classscope(attr='o')
    def test_change_price_issued_giftcard_used(self):
        gc = self.o.issued_gift_cards.create(currency='EUR', issued_in=self.op1)
        gc.transactions.create(value=20)
        with self.assertRaises(OrderError):
            self.ocm.change_price(self.op1, 25)

    @classscope(attr='o')
    def test_cancel_all_in_order(self):
        self.ocm.cancel(self.op1)
        self.ocm.cancel(self.op2)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        assert self.order.positions.count() == 2

    @classscope(attr='o')
    def test_empty(self):
        self.ocm.commit()

    @classscope(attr='o')
    def test_quota_unlimited(self):
        q = self.event.quotas.create(name='Test', size=None)
        q.products.add(self.shirt)
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.product == self.shirt

    @classscope(attr='o')
    def test_quota_full(self):
        q = self.event.quotas.create(name='Test', size=0)
        q.products.add(self.shirt)
        self.ocm.change_product(self.op1, self.shirt, None)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.product == self.ticket

    @classscope(attr='o')
    def test_quota_ignore(self):
        q = self.event.quotas.create(name='Test', size=0)
        q.products.add(self.shirt)
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit(check_quotas=False)
        self.op1.refresh_from_db()
        assert self.op1.product == self.shirt

    @classscope(attr='o')
    def test_quota_full_but_in_same(self):
        q = self.event.quotas.create(name='Test', size=0)
        q.products.add(self.shirt)
        q.products.add(self.ticket)
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.product == self.shirt

    @classscope(attr='o')
    def test_multiple_quotas_shared_full(self):
        q1 = self.event.quotas.create(name='Test', size=0)
        q2 = self.event.quotas.create(name='Test', size=2)
        q1.products.add(self.shirt)
        q1.products.add(self.ticket)
        q2.products.add(self.shirt)
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.product == self.shirt

    @classscope(attr='o')
    def test_multiple_quotas_unshared_full(self):
        q1 = self.event.quotas.create(name='Test', size=2)
        q2 = self.event.quotas.create(name='Test', size=0)
        q1.products.add(self.shirt)
        q1.products.add(self.ticket)
        q2.products.add(self.shirt)
        self.ocm.change_product(self.op1, self.shirt, None)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.product == self.ticket

    @classscope(attr='o')
    def test_multiple_items_success(self):
        q1 = self.event.quotas.create(name='Test', size=2)
        q1.products.add(self.shirt)
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.change_product(self.op2, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.op2.refresh_from_db()
        assert self.op1.product == self.shirt
        assert self.op2.product == self.shirt

    @classscope(attr='o')
    def test_multiple_items_quotas_partially_full(self):
        q1 = self.event.quotas.create(name='Test', size=1)
        q1.products.add(self.shirt)
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.change_product(self.op2, self.shirt, None)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        self.op1.refresh_from_db()
        self.op2.refresh_from_db()
        assert self.op1.product == self.ticket
        assert self.op2.product == self.ticket

    @classscope(attr='o')
    def test_payment_fee_calculation(self):
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_abs', Decimal('0.30'))
        self.ocm.change_price(self.op1, Decimal('24.00'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('47.30')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == prov.calculate_fee(self.order.total)
        assert fee.tax_rate == Decimal('19.00')
        assert round_decimal(fee.value * (1 - 100 / (100 + fee.tax_rate))) == fee.tax_value

    @classscope(attr='o')
    def test_pending_free_order_stays_pending(self):
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        self.ocm.change_price(self.op1, Decimal('0.00'))
        self.ocm.change_price(self.op2, Decimal('0.00'))
        self.ocm.commit()
        self.ocm = OrderChangeManager(self.order, None)
        self.order.refresh_from_db()
        assert self.order.total == Decimal('0.00')
        assert self.order.status == Order.STATUS_PAID
        self.order.status = Order.STATUS_PENDING
        self.ocm.cancel(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_PENDING

    @classscope(attr='o')
    def test_require_pending(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.product == self.shirt

    @classscope(attr='o')
    def test_change_price_to_free_marked_as_paid(self):
        self.ocm.change_price(self.op1, Decimal('0.00'))
        self.ocm.change_price(self.op2, Decimal('0.00'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == 0
        assert self.order.status == Order.STATUS_PAID
        assert self.order.payments.last().provider == 'free'

    @classscope(attr='o')
    def test_change_price_to_free_require_approval(self):
        self.order.require_approval = True
        self.order.save()
        self.ocm = OrderChangeManager(self.order, None)
        self.ocm.change_price(self.op1, Decimal('0.00'))
        self.ocm.change_price(self.op2, Decimal('0.00'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == 0
        assert self.order.status == Order.STATUS_PENDING

    @classscope(attr='o')
    def test_change_paid_same_price(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.ocm.change_product(self.op1, self.ticket2, None)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == 46
        assert self.order.status == Order.STATUS_PAID

    @classscope(attr='o')
    def test_change_paid_different_price(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.ocm.change_price(self.op1, Decimal('5.00'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('28.00')
        assert self.order.status == Order.STATUS_PAID

    @classscope(attr='o')
    def test_change_paid_to_pending(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=self.order.total,
        )
        self.ocm.change_price(self.op1, Decimal('25.00'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('48.00')
        assert self.order.pending_sum == Decimal('2.00')
        assert self.order.status == Order.STATUS_PENDING

    @classscope(attr='o')
    def test_change_paid_stays_paid_when_overpaid(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=self.order.total,
        )
        self.order.payments.create(
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('2.00'),
        )
        assert self.order.pending_sum == Decimal('-2.00')
        self.ocm.change_price(self.op1, Decimal('25.00'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('48.00')
        assert self.order.pending_sum == Decimal('0.00')
        assert self.order.status == Order.STATUS_PAID

    @classscope(attr='o')
    def test_add_item_quota_required(self):
        self.quota.delete()
        with self.assertRaises(OrderError):
            self.ocm.add_position(self.shirt, None, None, None)

    @classscope(attr='o')
    def test_add_item_success(self):
        self.ocm.add_position(self.shirt, None, None, None)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 3
        nop = self.order.positions.last()
        assert nop.product == self.shirt
        assert nop.price == self.shirt.default_price
        assert nop.tax_rate == self.shirt.tax_rule.rate
        assert round_decimal(nop.price * (1 - 100 / (100 + self.shirt.tax_rule.rate))) == nop.tax_value
        assert self.order.total == self.op1.price + self.op2.price + nop.price
        assert nop.positionid == 3

    @classscope(attr='o')
    def test_add_item_net_price_success(self):
        self.tr19.price_includes_tax = False
        self.tr19.save()
        self.ocm.add_position(self.shirt, None, None, None)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 3
        nop = self.order.positions.last()
        assert nop.product == self.shirt
        assert nop.price == Decimal('14.28')
        assert nop.tax_rate == self.shirt.tax_rule.rate
        assert round_decimal(nop.price * (1 - 100 / (100 + self.shirt.tax_rule.rate))) == nop.tax_value
        assert self.order.total == self.op1.price + self.op2.price + nop.price
        assert nop.positionid == 3

    @classscope(attr='o')
    def test_add_item_reverse_charge(self):
        self._enable_reverse_charge()
        self.ocm.add_position(self.shirt, None, None, None)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 3
        nop = self.order.positions.last()
        assert nop.product == self.shirt
        assert nop.price == Decimal('10.08')
        assert nop.tax_rate == Decimal('0.00')
        assert nop.tax_value == Decimal('0.00')
        assert self.order.total == self.op1.price + self.op2.price + nop.price
        assert nop.positionid == 3

    @classscope(attr='o')
    def test_add_item_custom_price(self):
        self.ocm.add_position(self.shirt, None, Decimal('13.00'), None)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 3
        nop = self.order.positions.last()
        assert nop.product == self.shirt
        assert nop.price == Decimal('13.00')
        assert nop.tax_rate == self.shirt.tax_rule.rate
        assert round_decimal(nop.price * (1 - 100 / (100 + self.shirt.tax_rule.rate))) == nop.tax_value
        assert self.order.total == self.op1.price + self.op2.price + nop.price

    @classscope(attr='o')
    def test_add_item_custom_price_tax_always_included(self):
        self.tr19.price_includes_tax = False
        self.tr19.save()
        self.ocm.add_position(self.shirt, None, Decimal('11.90'), None)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 3
        nop = self.order.positions.last()
        assert nop.product == self.shirt
        assert nop.price == Decimal('11.90')
        assert nop.tax_rate == self.shirt.tax_rule.rate
        assert round_decimal(nop.price * (1 - 100 / (100 + self.shirt.tax_rule.rate))) == nop.tax_value
        assert self.order.total == self.op1.price + self.op2.price + nop.price

    @classscope(attr='o')
    def test_add_item_quota_full(self):
        q1 = self.event.quotas.create(name='Test', size=0)
        q1.products.add(self.shirt)
        self.ocm.add_position(self.shirt, None, None, None)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        assert self.order.positions.count() == 2

    @classscope(attr='o')
    def test_add_item_addon(self):
        self.shirt.category = self.event.categories.create(name='Add-ons', is_addon=True)
        self.ticket.addons.create(addon_category=self.shirt.category)
        self.ocm.add_position(self.shirt, None, Decimal('13.00'), self.op1)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 3
        nop = self.order.positions.last()
        assert nop.product == self.shirt
        assert nop.addon_to == self.op1

    @classscope(attr='o')
    def test_add_item_addon_invalid(self):
        with self.assertRaises(OrderError):
            self.ocm.add_position(self.shirt, None, Decimal('13.00'), self.op1)
        self.shirt.category = self.event.categories.create(name='Add-ons', is_addon=True)
        with self.assertRaises(OrderError):
            self.ocm.add_position(self.shirt, None, Decimal('13.00'), None)

    @classscope(attr='o')
    def test_add_item_subevent_required(self):
        self.event.has_subevents = True
        self.event.save()
        with self.assertRaises(OrderError):
            self.ocm.add_position(self.ticket, None, None, None)

    @classscope(attr='o')
    def test_add_item_subevent_price(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        SubEventItem.objects.create(subevent=se1, product=self.ticket, price=12)
        self.quota.subevent = se1
        self.quota.save()

        self.ocm.add_position(self.ticket, None, None, subevent=se1)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.positions.count() == 3
        nop = self.order.positions.last()
        assert nop.product == self.ticket
        assert nop.price == Decimal('12.00')
        assert nop.subevent == se1

    @classscope(attr='o')
    def test_reissue_invoice(self):
        generate_invoice(self.order)
        assert self.order.invoices.count() == 1
        self.ocm.add_position(self.ticket, None, Decimal('0.00'))
        self.ocm.commit()
        assert self.order.invoices.count() == 3

    @classscope(attr='o')
    def test_no_new_invoice_for_free_order(self):
        generate_invoice(self.order)
        assert self.order.invoices.count() == 1
        self.ocm.change_price(self.op1, Decimal('0.00'))
        self.ocm.change_price(self.op2, Decimal('0.00'))
        self.ocm.commit()
        assert self.order.invoices.count() == 2

    @classscope(attr='o')
    def test_reissue_invoice_disabled(self):
        self.ocm.reissue_invoice = False
        generate_invoice(self.order)
        assert self.order.invoices.count() == 1
        self.ocm.add_position(self.ticket, None, Decimal('0.00'))
        self.ocm.commit()
        assert self.order.invoices.count() == 1

    @classscope(attr='o')
    def test_dont_reissue_invoice_on_free_product_changes(self):
        self.event.settings.invoice_include_free = False
        generate_invoice(self.order)
        assert self.order.invoices.count() == 1
        self.ocm.add_position(self.ticket, None, Decimal('0.00'))
        self.ocm.commit()
        assert self.order.invoices.count() == 1

    @classscope(attr='o')
    def test_recalculate_country_rate(self):
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_abs', Decimal('0.30'))
        self.ocm._recalculate_total_and_payment_fee()

        assert self.order.total == Decimal('46.30')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == prov.calculate_fee(self.order.total)
        assert fee.tax_rate == Decimal('19.00')
        assert fee.tax_value == Decimal('0.05')

        self.ocm = OrderChangeManager(self.order, None)

        self._enable_reverse_charge()
        self.tr7.custom_rules = json.dumps([{'country': 'AT', 'address_type': '', 'action': 'vat', 'rate': '100.00'}])
        self.tr7.save()

        self.ocm.recalculate_taxes(keep='net')
        self.ocm.commit()
        ops = list(self.order.positions.all())
        for op in ops:
            assert op.price == Decimal('43.00')
            assert op.tax_value == Decimal('21.50')
            assert op.tax_rate == Decimal('100.00')

        assert self.order.total == Decimal('86.00') + fee.value

    @classscope(attr='o')
    def test_recalculate_country_rate_keep_gross(self):
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_abs', Decimal('0.30'))
        self.ocm._recalculate_total_and_payment_fee()

        assert self.order.total == Decimal('46.30')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == prov.calculate_fee(self.order.total)
        assert fee.tax_rate == Decimal('19.00')
        assert fee.tax_value == Decimal('0.05')

        self.ocm = OrderChangeManager(self.order, None)

        self._enable_reverse_charge()
        self.tr7.custom_rules = json.dumps([{'country': 'AT', 'address_type': '', 'action': 'vat', 'rate': '100.00'}])
        self.tr7.save()

        self.ocm.recalculate_taxes(keep='gross')
        self.ocm.commit()
        ops = list(self.order.positions.all())
        for op in ops:
            assert op.price == Decimal('23.00')
            assert op.tax_value == Decimal('11.50')
            assert op.tax_rate == Decimal('100.00')

        assert self.order.total == Decimal('46.00') + fee.value

    @classscope(attr='o')
    def test_recalculate_reverse_charge(self):
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_abs', Decimal('0.30'))
        self.ocm._recalculate_total_and_payment_fee()

        assert self.order.total == Decimal('46.30')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == prov.calculate_fee(self.order.total)
        assert fee.tax_rate == Decimal('19.00')
        assert fee.tax_value == Decimal('0.05')

        self.ocm = OrderChangeManager(self.order, None)
        ia = self._enable_reverse_charge()
        self.ocm.recalculate_taxes()
        self.ocm.commit()
        ops = list(self.order.positions.all())
        for op in ops:
            assert op.price == Decimal('21.50')
            assert op.tax_value == Decimal('0.00')
            assert op.tax_rate == Decimal('0.00')

        assert self.order.total == Decimal('43.30')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == prov.calculate_fee(self.order.total)
        assert fee.tax_rate == Decimal('0.00')
        assert fee.tax_value == Decimal('0.00')

        ia.vat_id_validated = False
        ia.save()

        self.ocm = OrderChangeManager(self.order, None)
        self.ocm.recalculate_taxes()
        self.ocm.commit()
        ops = list(self.order.positions.all())
        for op in ops:
            assert op.price == Decimal('23.01')  # sic. we can't really avoid it.
            assert op.tax_value == Decimal('1.51')
            assert op.tax_rate == Decimal('7.00')

        assert self.order.total == Decimal('46.32')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == prov.calculate_fee(self.order.total)
        assert fee.tax_rate == Decimal('19.00')
        assert fee.tax_value == Decimal('0.05')

    @classscope(attr='o')
    def test_split_simple(self):
        old_secret = self.op2.secret
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()
        assert self.order.total == Decimal('23.00')
        assert self.order.positions.count() == 1
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('23.00')
        assert o2.positions.count() == 1
        assert o2.code != self.order.code
        assert o2.secret != self.order.secret
        assert o2.datetime > self.order.datetime
        assert self.op2.secret != old_secret
        assert not self.order.invoices.exists()
        assert not o2.invoices.exists()

    @classscope(attr='o')
    def test_split_require_approval(self):
        self.op2.product.require_approval = True
        self.op2.product.save()
        self.order.require_approval = True
        self.order.save()
        old_secret = self.op2.secret
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()
        assert self.order.total == Decimal('23.00')
        assert self.order.positions.count() == 1
        assert self.op2.order != self.order
        assert self.op2.order.require_approval
        o2 = self.op2.order
        assert o2.total == Decimal('23.00')
        assert o2.positions.count() == 1
        assert o2.code != self.order.code
        assert o2.secret != self.order.secret
        assert o2.datetime > self.order.datetime
        assert self.op2.secret != old_secret
        assert not self.order.invoices.exists()
        assert not o2.invoices.exists()

    @classscope(attr='o')
    def test_split_pending_payment_fees(self):
        # Set payment fees
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_percent', Decimal('2.00'))
        prov.settings.set('_fee_abs', Decimal('1.00'))
        prov.settings.set('_fee_reverse_calc', False)
        self.ocm.change_price(self.op1, Decimal('23.00'))
        self.ocm.commit()
        self.ocm = OrderChangeManager(self.order, None)
        self.order.refresh_from_db()
        assert self.order.total == Decimal('47.92')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('1.92')
        assert fee.tax_rate == Decimal('19.00')

        # Split
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('24.46')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('1.46')
        assert fee.tax_rate == Decimal('19.00')
        assert self.order.positions.count() == 1
        assert self.order.fees.count() == 1

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('24.46')
        fee = o2.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('1.46')
        assert fee.tax_rate == Decimal('19.00')
        assert o2.positions.count() == 1
        assert o2.fees.count() == 1

    @classscope(attr='o')
    def test_split_paid_no_payment_fees(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=self.order.total,
        )

        # Split
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('23.00')
        assert not self.order.fees.exists()
        assert self.order.pending_sum == Decimal('0.00')
        r = self.order.refunds.last()
        assert r.provider == 'offsetting'
        assert r.amount == Decimal('23.00')
        assert r.state == OrderRefund.REFUND_STATE_DONE

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('23.00')
        assert o2.status == Order.STATUS_PAID
        assert o2.positions.count() == 1
        assert o2.fees.count() == 0
        assert o2.pending_sum == Decimal('0.00')
        p = o2.payments.last()
        assert p.provider == 'offsetting'
        assert p.amount == Decimal('23.00')
        assert p.state == OrderPayment.PAYMENT_STATE_CONFIRMED

    @classscope(attr='o')
    def test_split_and_change_higher(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=self.order.total,
        )

        # Split
        self.ocm.change_price(self.op2, Decimal('42.00'))
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('23.00')
        assert not self.order.fees.exists()
        assert self.order.status == Order.STATUS_PAID
        assert self.order.pending_sum == Decimal('0.00')
        r = self.order.refunds.last()
        assert r.provider == 'offsetting'
        assert r.amount == Decimal('23.00')
        assert r.state == OrderRefund.REFUND_STATE_DONE

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('42.00')
        assert o2.status == Order.STATUS_PENDING
        assert o2.positions.count() == 1
        assert o2.fees.count() == 0
        assert o2.pending_sum == Decimal('19.00')
        p = o2.payments.last()
        assert p.provider == 'offsetting'
        assert p.amount == Decimal('23.00')
        assert p.state == OrderPayment.PAYMENT_STATE_CONFIRMED

    @classscope(attr='o')
    def test_split_and_change_lower(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=self.order.total,
        )

        # Split
        self.ocm.change_price(self.op2, Decimal('10.00'))
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('23.00')
        assert not self.order.fees.exists()
        assert self.order.status == Order.STATUS_PAID
        assert self.order.pending_sum == Decimal('-13.00')
        r = self.order.refunds.last()
        assert r.provider == 'offsetting'
        assert r.amount == Decimal('10.00')
        assert r.state == OrderRefund.REFUND_STATE_DONE

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('10.00')
        assert o2.status == Order.STATUS_PAID
        assert o2.positions.count() == 1
        assert o2.fees.count() == 0
        assert o2.pending_sum == Decimal('0.00')
        p = o2.payments.last()
        assert p.provider == 'offsetting'
        assert p.amount == Decimal('10.00')
        assert p.state == OrderPayment.PAYMENT_STATE_CONFIRMED

    @classscope(attr='o')
    def test_split_invoice_address(self):
        ia = InvoiceAddress.objects.create(
            order=self.order,
            is_business=True,
            vat_id='ATU1234567',
            vat_id_validated=True,
            country=Country('AT'),
            company='Sample',
        )

        # Split
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('23.00')
        assert self.order.invoice_address == ia

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        o2.refresh_from_db()
        ia = InvoiceAddress.objects.get(pk=ia.pk)
        assert o2.total == Decimal('23.00')
        assert o2.positions.count() == 1
        assert o2.invoice_address != ia
        assert o2.invoice_address.company == 'Sample'

    @classscope(attr='o')
    def test_change_price_of_pending_order_with_payment(self):
        self.order.status = Order.STATUS_PENDING
        self.order.save()
        assert self.order.payments.last().state == OrderPayment.PAYMENT_STATE_CREATED
        assert self.order.payments.last().amount == Decimal('46.00')

        self.ocm.change_price(self.op1, Decimal('27.00'))
        self.ocm.commit()

        assert self.order.payments.last().state == OrderPayment.PAYMENT_STATE_CANCELED
        assert self.order.payments.last().amount == Decimal('46.00')

    @classscope(attr='o')
    def test_split_reverse_charge(self):
        ia = self._enable_reverse_charge()

        # Set payment fees
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_percent', Decimal('2.00'))
        prov.settings.set('_fee_reverse_calc', False)
        self.ocm.recalculate_taxes()
        self.ocm.commit()
        self.ocm = OrderChangeManager(self.order, None)
        self.order.refresh_from_db()

        # Check if reverse charge is active
        assert self.order.total == Decimal('43.86')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('0.86')
        assert fee.tax_rate == Decimal('0.00')
        self.op1.refresh_from_db()
        self.op2.refresh_from_db()
        assert self.op1.price == Decimal('21.50')
        assert self.op2.price == Decimal('21.50')

        # Split
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('21.93')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('0.43')
        assert fee.tax_rate == Decimal('0.00')
        assert fee.tax_value == Decimal('0.00')
        assert self.order.positions.count() == 1
        assert self.order.fees.count() == 1
        assert self.order.positions.first().price == Decimal('21.50')
        assert self.order.positions.first().tax_value == Decimal('0.00')

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('21.93')
        fee = o2.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('0.43')
        assert fee.tax_rate == Decimal('0.00')
        assert fee.tax_value == Decimal('0.00')
        assert o2.positions.count() == 1
        assert o2.positions.first().price == Decimal('21.50')
        assert o2.positions.first().tax_value == Decimal('0.00')
        assert o2.fees.count() == 1
        ia = InvoiceAddress.objects.get(pk=ia.pk)
        assert o2.invoice_address != ia
        assert o2.invoice_address.vat_id_validated is True

    @classscope(attr='o')
    def test_split_other_fees(self):
        # Check if reverse charge is active
        self.order.fees.create(
            fee_type=OrderFee.FEE_TYPE_SHIPPING,
            tax_rule=self.tr19,
            value=Decimal('2.50'),
        )
        self.order.total += Decimal('2.50')
        self.order.save()

        # Split
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('25.50')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_SHIPPING)
        assert fee.value == Decimal('2.50')
        assert fee.tax_value == Decimal('0.40')
        assert self.order.positions.count() == 1
        assert self.order.fees.count() == 1

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('25.50')
        fee = o2.fees.get(fee_type=OrderFee.FEE_TYPE_SHIPPING)
        assert fee.value == Decimal('2.50')
        assert fee.tax_value == Decimal('0.40')
        assert o2.positions.count() == 1
        assert o2.positions.first().price == Decimal('23.00')
        assert o2.fees.count() == 1

    @classscope(attr='o')
    def test_split_to_empty(self):
        self.ocm.split(self.op1)
        self.ocm.split(self.op2)
        with self.assertRaises(OrderError):
            self.ocm.commit()

    @classscope(attr='o')
    def test_split_paid_payment_fees(self):
        # Set payment fees
        self.event.settings.set('tax_rate_default', self.tr19.pk)
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_percent', Decimal('2.00'))
        prov.settings.set('_fee_abs', Decimal('1.00'))
        prov.settings.set('_fee_reverse_calc', False)
        self.ocm.change_price(self.op1, Decimal('23.00'))
        self.ocm.commit()
        self.ocm = OrderChangeManager(self.order, None)
        self.order.refresh_from_db()
        assert self.order.total == Decimal('47.92')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('1.92')
        assert fee.tax_rate == Decimal('19.00')

        self.order.status = Order.STATUS_PAID
        self.order.save()
        payment = self.order.payments.first()
        payment.state = OrderPayment.PAYMENT_STATE_CONFIRMED
        payment.save()

        # Split
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()

        # First order
        assert self.order.total == Decimal('24.92')
        fee = self.order.fees.get(fee_type=OrderFee.FEE_TYPE_PAYMENT)
        assert fee.value == Decimal('1.92')
        assert fee.tax_rate == Decimal('19.00')
        assert self.order.positions.count() == 1
        assert self.order.fees.count() == 1

        # New order
        assert self.op2.order != self.order
        o2 = self.op2.order
        assert o2.total == Decimal('23.00')
        assert o2.fees.count() == 0

    @classscope(attr='o')
    def test_split_invoice(self):
        generate_invoice(self.order)
        assert self.order.invoices.count() == 1
        assert self.order.invoices.last().lines.count() == 2
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()
        o2 = self.op2.order

        assert self.order.invoices.count() == 3
        assert self.order.invoices.last().lines.count() == 1
        assert o2.invoices.count() == 1
        assert o2.invoices.last().lines.count() == 1

    @classscope(attr='o')
    def test_split_to_free_invoice(self):
        self.event.settings.invoice_include_free = False
        self.ocm.change_price(self.op2, Decimal('0.00'))
        self.ocm.commit()
        self.ocm = OrderChangeManager(self.order, None)
        self.op2.refresh_from_db()
        self.ocm._invoice_dirty = False

        generate_invoice(self.order)
        assert self.order.invoices.count() == 1
        assert self.order.invoices.last().lines.count() == 1
        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()
        o2 = self.op2.order

        assert self.order.invoices.count() == 1
        assert self.order.invoices.last().lines.count() == 1
        assert o2.invoices.count() == 0

    @classscope(attr='o')
    def test_split_to_original_free(self):
        self.ocm.change_price(self.op2, Decimal('0.00'))
        self.ocm.commit()
        self.ocm = OrderChangeManager(self.order, None)
        self.op2.refresh_from_db()

        self.ocm.split(self.op1)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()
        o2 = self.op1.order

        assert self.order.total == Decimal('0.00')
        assert self.order.status == Order.STATUS_PAID
        assert o2.total == Decimal('23.00')
        assert o2.status == Order.STATUS_PENDING

    @classscope(attr='o')
    def test_split_to_new_free(self):
        self.ocm.change_price(self.op2, Decimal('0.00'))
        self.ocm.commit()
        self.ocm = OrderChangeManager(self.order, None)
        self.op2.refresh_from_db()

        self.ocm.split(self.op2)
        self.ocm.commit()
        self.order.refresh_from_db()
        self.op2.refresh_from_db()
        o2 = self.op2.order

        assert self.order.total == Decimal('23.00')
        assert self.order.status == Order.STATUS_PENDING
        assert o2.total == Decimal('0.00')
        assert o2.status == Order.STATUS_PAID

    @classscope(attr='o')
    def test_change_seat_circular(self):
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.op2.seat = self.seat_a2
        self.op2.save()
        self.ocm.change_seat(self.op1, self.seat_a2)
        self.ocm.change_seat(self.op2, self.seat_a1)
        self.ocm.commit()
        self.op1.refresh_from_db()
        self.op2.refresh_from_db()
        assert self.op1.seat == self.seat_a2
        assert self.op2.seat == self.seat_a1

    @classscope(attr='o')
    def test_change_seat_duplicate(self):
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.op2.seat = self.seat_a2
        self.op2.save()
        self.ocm.change_seat(self.op1, self.seat_a2)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat == self.seat_a1

    @classscope(attr='o')
    def test_change_seat_and_cancel(self):
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.op2.seat = self.seat_a2
        self.op2.save()
        self.ocm.change_seat(self.op1, self.seat_a2)
        self.ocm.cancel(self.op2)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat == self.seat_a2

    @classscope(attr='o')
    def test_change_seat(self):
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.ocm.change_seat(self.op1, self.seat_a2)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat == self.seat_a2

    @classscope(attr='o')
    def test_change_add_seat(self):
        # does this make sense or do we block it based on the item? this is currently not reachable through the UI
        self.ocm.change_seat(self.op1, self.seat_a1)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat == self.seat_a1

    @classscope(attr='o')
    def test_remove_seat(self):
        # does this make sense or do we block it based on the item? this is currently not reachable through the UI
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.ocm.change_seat(self.op1, None)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat is None

    @classscope(attr='o')
    def test_add_with_seat(self):
        self.ocm.add_position(self.stalls, None, price=Decimal('13.00'), seat=self.seat_a3)
        self.ocm.commit()
        op3 = self.order.positions.last()
        assert op3.product == self.stalls
        assert op3.seat == self.seat_a3

    @classscope(attr='o')
    def test_add_with_taken_seat(self):
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.ocm.add_position(self.stalls, None, price=Decimal('13.00'), seat=self.seat_a1)
        with self.assertRaises(OrderError):
            self.ocm.commit()

    @classscope(attr='o')
    def test_add_with_seat_not_required_if_no_choice(self):
        self.event.settings.seating_choice = False
        self.ocm.add_position(self.stalls, None, price=Decimal('13.00'))

    @classscope(attr='o')
    def test_add_with_seat_not_required(self):
        with self.assertRaises(OrderError):
            self.ocm.add_position(self.stalls, None, price=Decimal('13.00'))

    @classscope(attr='o')
    def test_add_with_seat_forbidden(self):
        with self.assertRaises(OrderError):
            self.ocm.add_position(self.ticket, None, price=Decimal('13.00'), seat=self.seat_a1)

    @classscope(attr='o')
    def test_add_with_seat_blocked(self):
        self.seat_a1.blocked = True
        self.seat_a1.save()
        self.ocm.add_position(self.stalls, None, price=Decimal('13.00'), seat=self.seat_a1)
        with self.assertRaises(OrderError):
            self.ocm.commit()

    @classscope(attr='o')
    def test_change_seat_to_blocked(self):
        self.seat_a2.blocked = True
        self.seat_a2.save()
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.ocm.change_seat(self.op1, self.seat_a2)
        with self.assertRaises(OrderError):
            self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat == self.seat_a1

    @classscope(attr='o')
    def test_change_seat_require_subevent_change(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        self.op1.subevent = se1
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.quota.subevent = se2
        self.quota.save()
        self.seat_a1.subevent = se1
        self.seat_a1.save()
        self.seat_a2.subevent = se2
        self.seat_a2.save()
        self.ocm.change_seat(self.op1, self.seat_a2)
        with self.assertRaises(OrderError):
            self.ocm.commit()

    @classscope(attr='o')
    def test_change_subevent_require_seat_change(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        self.op1.subevent = se1
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.quota.subevent = se2
        self.quota.save()
        self.seat_a1.subevent = se1
        self.seat_a1.save()
        self.seat_a2.subevent = se2
        self.seat_a2.save()
        self.ocm.change_subevent(self.op1, se2)
        with self.assertRaises(OrderError):
            self.ocm.commit()

    @classscope(attr='o')
    def test_change_subevent_and_seat(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        self.op1.subevent = se1
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.quota.subevent = se2
        self.quota.save()
        self.seat_a1.subevent = se1
        self.seat_a1.save()
        self.seat_a2.subevent = se2
        self.seat_a2.save()
        self.ocm.change_subevent(self.op1, se2)
        self.ocm.change_seat(self.op1, self.seat_a2)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat == self.seat_a2
        assert self.op1.subevent == se2

    @classscope(attr='o')
    def test_change_seat_inside_subevent(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        self.op1.subevent = se1
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.seat_a1.subevent = se1
        self.seat_a1.save()
        self.seat_a2.subevent = se1
        self.seat_a2.save()
        self.ocm.change_seat(self.op1, self.seat_a2)
        self.ocm.commit()
        self.op1.refresh_from_db()
        assert self.op1.seat == self.seat_a2
        assert self.op1.subevent == se1

    @classscope(attr='o')
    def test_add_with_seat_and_subevent_mismatch(self):
        self.event.has_subevents = True
        self.event.save()
        se1 = self.event.subevents.create(name='Foo', date_from=now())
        se2 = self.event.subevents.create(name='Bar', date_from=now())
        self.quota.subevent = se2
        self.quota.save()
        self.seat_a1.subevent = se1
        self.seat_a1.save()
        self.ocm.change_subevent(self.op1, se2)
        with self.assertRaises(OrderError):
            self.ocm.add_position(
                self.ticket,
                None,
                price=Decimal('13.00'),
                subevent=se2,
                seat=self.seat_a1,
            )

    @classscope(attr='o')
    def test_fee_change_value(self):
        fee = self.order.fees.create(fee_type='shipping', value=Decimal('5.00'))
        self.order.total += Decimal('5.00')
        self.order.save()
        self.ocm.change_fee(fee, Decimal('3.50'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('49.50')
        fee.refresh_from_db()
        assert fee.value == Decimal('3.50')

    @classscope(attr='o')
    def test_fee_change_value_tax_rate(self):
        fee = self.order.fees.create(fee_type='shipping', value=Decimal('5.00'), tax_rule=self.tr19)
        self.order.total += Decimal('5.00')
        self.order.save()
        self.ocm.change_fee(fee, Decimal('3.50'))
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('49.50')
        fee.refresh_from_db()
        assert fee.value == Decimal('3.50')
        assert fee.tax_rate == Decimal('19.00')
        assert fee.tax_value == Decimal('0.56')

    @classscope(attr='o')
    def test_fee_cancel(self):
        fee = self.order.fees.create(fee_type='shipping', value=Decimal('5.00'))
        self.order.total += Decimal('5.00')
        self.order.save()
        self.ocm.cancel_fee(fee)
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('46.00')
        fee.refresh_from_db()
        assert fee.canceled

    @classscope(attr='o')
    def test_clear_out_order(self):
        self.event.settings.ticket_secret_generator = 'pretix_sig1'
        op = self.order.positions.first()
        s = op.secret
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(
            amount=self.order.total,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='manual',
        )
        cancel_order(self.order, cancellation_fee=Decimal('5.00'))
        self.order.refresh_from_db()
        assert self.order.total == Decimal('5.00')
        self.ocm.cancel_fee(self.order.fees.get())
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('0.00')
        assert self.order.status == Order.STATUS_CANCELED
        assert op.secret == s

    @classscope(attr='o')
    def test_clear_out_order_change_secrets(self):
        self.event.settings.ticket_secret_generator = 'pretix_sig1'
        op = self.order.positions.first()
        s = op.secret
        self.order.status = Order.STATUS_PAID
        self.order.save()
        self.order.payments.create(
            amount=self.order.total,
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            provider='manual',
        )
        cancel_order(self.order, cancellation_fee=Decimal('5.00'))
        self.order.refresh_from_db()
        assert self.order.total == Decimal('5.00')
        self.ocm.cancel_fee(self.order.fees.get())
        self.ocm.commit()
        self.order.refresh_from_db()
        assert self.order.total == Decimal('0.00')
        assert self.order.status == Order.STATUS_CANCELED
        op.refresh_from_db()
        assert op.secret != s

    @classscope(attr='o')
    def test_auto_change_payment_fee(self):
        fee2 = self.order.fees.create(fee_type=OrderFee.FEE_TYPE_SHIPPING, value=Decimal('0.50'))
        fee = self.order.fees.create(fee_type=OrderFee.FEE_TYPE_PAYMENT, value=Decimal('0.46'))
        self.order.status = Order.STATUS_PAID
        self.order.total = Decimal('51.1')
        self.order.save()

        self.order.payments.create(
            state=OrderPayment.PAYMENT_STATE_PENDING,
            amount=Decimal('48.5'),
            fee=fee,
            provider='banktransfer',
        )
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_percent', Decimal('10.00'))
        prov.settings.set('_fee_reverse_calc', False)

        self.ocm.cancel_fee(fee2)
        self.ocm.commit()
        assert self.order.total == Decimal('50.6')
        fee.refresh_from_db()
        assert fee.value == Decimal('4.6')

    @classscope(attr='o')
    def test_change_payment_fee(self):
        fee = self.order.fees.create(fee_type=OrderFee.FEE_TYPE_PAYMENT, value=Decimal('0.46'))
        self.order.status = Order.STATUS_PAID
        self.order.total = Decimal('50.60')
        self.order.save()

        self.order.payments.create(
            state=OrderPayment.PAYMENT_STATE_PENDING,
            amount=Decimal('48.5'),
            fee=fee,
            provider='banktransfer',
        )
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_percent', Decimal('10.00'))
        prov.settings.set('_fee_reverse_calc', False)

        self.ocm.change_fee(fee, Decimal('0.2'))
        self.ocm.commit()
        fee.refresh_from_db()
        assert fee.value == Decimal('0.20')
        self.order.refresh_from_db()
        assert self.order.total == Decimal('46.20')

    @classscope(attr='o')
    def test_cancel_payment_fee(self):
        fee = self.order.fees.create(fee_type=OrderFee.FEE_TYPE_PAYMENT, value=Decimal('0.46'))
        self.order.status = Order.STATUS_PAID
        self.order.total = Decimal('50.60')
        self.order.save()

        self.order.payments.create(
            state=OrderPayment.PAYMENT_STATE_PENDING,
            amount=Decimal('48.5'),
            fee=fee,
            provider='banktransfer',
        )
        prov = self.ocm._get_payment_provider()
        prov.settings.set('_fee_percent', Decimal('10.00'))
        prov.settings.set('_fee_reverse_calc', False)

        self.ocm.cancel_fee(fee)
        self.ocm.commit()
        fee.refresh_from_db()
        assert fee.canceled
        self.order.refresh_from_db()
        assert self.order.total == Decimal('46.00')

    @classscope(attr='o')
    def test_change_taxrate(self):
        self.ocm.change_tax_rule(self.op1, self.tr19)
        self.ocm.commit()
        self.order.refresh_from_db()
        nop = self.order.positions.first()
        assert nop.price == Decimal('23.00')
        assert nop.tax_rule != self.ticket.tax_rule
        assert nop.tax_rate == self.tr19.rate
        assert round_decimal(nop.price * (1 - 100 / (100 + self.tr19.rate))) == nop.tax_value

    @classscope(attr='o')
    def test_change_taxrate_and_product(self):
        self.ocm.change_product(self.op1, self.shirt, None)
        self.ocm.change_tax_rule(self.op1, self.tr7)
        self.ocm.commit()
        self.order.refresh_from_db()
        nop = self.order.positions.first()
        assert nop.product == self.shirt
        assert nop.price == Decimal('23.00')
        assert nop.tax_rule != self.shirt.tax_rule
        assert nop.tax_rate == self.tr7.rate
        assert round_decimal(nop.price * (1 - 100 / (100 + self.tr7.rate))) == nop.tax_value

    @classscope(attr='o')
    def test_change_taxrate_to_reverse_charge(self):
        self.tr19.eu_reverse_charge = True
        self.tr19.home_country = Country('DE')
        self.tr19.save()
        InvoiceAddress.objects.create(
            order=self.order,
            is_business=True,
            vat_id='ATU1234567',
            vat_id_validated=True,
            country=Country('AT'),
        )

        self.ocm.change_tax_rule(self.op1, self.tr19)
        self.ocm.commit()
        self.order.refresh_from_db()
        nop = self.order.positions.first()
        assert nop.price == Decimal('23.00')
        assert nop.tax_rule == self.tr19
        assert nop.tax_rate == Decimal('0.00')
        assert nop.tax_value == Decimal('0.00')

    @classscope(attr='o')
    def test_change_taxrate_to_country_specific(self):
        self.tr19.eu_reverse_charge = True
        self.tr19.custom_rules = json.dumps([{'country': 'AT', 'address_type': '', 'action': 'vat', 'rate': '100.00'}])
        self.tr19.save()
        InvoiceAddress.objects.create(
            order=self.order,
            is_business=True,
            vat_id='ATU1234567',
            vat_id_validated=True,
            country=Country('AT'),
        )

        self.ocm.change_tax_rule(self.op1, self.tr19)
        self.ocm.commit()
        self.order.refresh_from_db()
        nop = self.order.positions.first()
        assert nop.price == Decimal('23.00')
        assert nop.tax_rule == self.tr19
        assert nop.tax_rate == Decimal('100.00')
        assert nop.tax_value == Decimal('11.50')

    @classscope(attr='o')
    def test_change_taxrate_from_reverse_charge(self):
        self.tr7.eu_reverse_charge = True
        self.tr7.home_country = Country('DE')
        self.tr7.save()
        nop = self.order.positions.first()
        nop.tax_value = Decimal('0.00')
        nop.tax_rate = Decimal('0.00')
        nop.save()
        InvoiceAddress.objects.create(
            order=self.order,
            is_business=True,
            vat_id='ATU1234567',
            vat_id_validated=True,
            country=Country('AT'),
        )

        self.ocm.change_tax_rule(self.op1, self.tr19)
        self.ocm.commit()
        self.order.refresh_from_db()
        nop = self.order.positions.first()
        assert nop.price == Decimal('23.00')
        assert nop.tax_rule == self.tr19
        assert nop.tax_rate == Decimal('19.00')
        assert nop.tax_value == Decimal('3.67')


@pytest.mark.django_db
def test_autocheckin(clist_autocheckin, event):
    today = now()
    tr7 = event.tax_rules.create(rate=Decimal('17.00'))
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        tax_rule=tr7,
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert 'web' in clist_autocheckin.auto_checkin_sales_channels
    assert order.positions.first().checkins.first().auto_checked_in

    clist_autocheckin.auto_checkin_sales_channels = []
    clist_autocheckin.save()

    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
    )[0]
    assert clist_autocheckin.auto_checkin_sales_channels == []
    assert order.positions.first().checkins.count() == 0


@pytest.mark.django_db
def test_saleschannel_testmode_restriction(event):
    today = now()
    tr7 = event.tax_rules.create(rate=Decimal('17.00'))
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        tax_rule=tr7,
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )

    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
        sales_channel='web',
    )[0]
    assert not order.testmode

    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
        sales_channel=FoobazSalesChannel.identifier,
    )[0]
    assert not order.testmode

    event.testmode = True
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
        sales_channel='web',
    )[0]
    assert order.testmode

    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=today,
        payment_provider=FreeOrderProvider(event),
        locale='de',
        sales_channel=FoobazSalesChannel.identifier,
    )[0]
    assert not order.testmode


@pytest.mark.django_db
def test_giftcard_multiple(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    gc1 = event.organizer.issued_gift_cards.create(currency='EUR')
    gc1.transactions.create(value=12)
    gc2 = event.organizer.issued_gift_cards.create(currency='EUR')
    gc2.transactions.create(value=12)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=now(),
        payment_provider=BankTransfer(event),
        locale='de',
        gift_cards=[gc1.pk, gc2.pk],
    )[0]
    assert order.payments.count() == 3
    assert order.payments.get(info__icontains=gc1.pk).amount == Decimal('12.00')
    assert order.payments.get(info__icontains=gc2.pk).amount == Decimal('11.00')
    assert gc1.value == 0
    assert gc2.value == 1


@pytest.mark.django_db
def test_giftcard_partial(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    gc1 = event.organizer.issued_gift_cards.create(currency='EUR')
    gc1.transactions.create(value=12)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=now(),
        payment_provider=BankTransfer(event),
        locale='de',
        gift_cards=[gc1.pk],
    )[0]
    assert order.payments.count() == 2
    assert order.payments.get(info__icontains=gc1.pk).amount == Decimal('12.00')
    assert order.payments.get(provider='banktransfer').amount == Decimal('11.00')
    assert gc1.value == 0


@pytest.mark.django_db
def test_giftcard_payment_fee(event):
    event.settings.set('payment_banktransfer__fee_percent', Decimal('10.00'))
    event.settings.set('payment_banktransfer__fee_reverse_calc', False)
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    gc1 = event.organizer.issued_gift_cards.create(currency='EUR')
    gc1.transactions.create(value=12)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=now(),
        payment_provider=BankTransfer(event),
        locale='de',
        gift_cards=[gc1.pk],
    )[0]
    assert order.payments.count() == 2
    assert order.payments.get(info__icontains=gc1.pk).amount == Decimal('12.00')
    assert order.payments.get(provider='banktransfer').amount == Decimal('12.10')
    assert order.fees.get().value == Decimal('1.10')
    assert gc1.value == 0


@pytest.mark.django_db
def test_giftcard_invalid_currency(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    gc1 = event.organizer.issued_gift_cards.create(currency='USD')
    gc1.transactions.create(value=12)
    with pytest.raises(OrderError):
        _create_order(
            event,
            email='dummy@example.org',
            positions=[cp1],
            now_dt=now(),
            payment_provider=BankTransfer(event),
            locale='de',
            gift_cards=[gc1.pk],
        )[0]


@pytest.mark.django_db
def test_giftcard_invalid_organizer(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    o2 = Organizer.objects.create(slug='foo', name='bar')
    gc1 = o2.issued_gift_cards.create(currency='EUR')
    gc1.transactions.create(value=12)
    with pytest.raises(OrderError):
        _create_order(
            event,
            email='dummy@example.org',
            positions=[cp1],
            now_dt=now(),
            payment_provider=BankTransfer(event),
            locale='de',
            gift_cards=[gc1.pk],
        )[0]


@pytest.mark.django_db
def test_giftcard_test_mode_invalid(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    gc1 = event.organizer.issued_gift_cards.create(currency='EUR', testmode=True)
    gc1.transactions.create(value=12)
    with pytest.raises(OrderError):
        _create_order(
            event,
            email='dummy@example.org',
            positions=[cp1],
            now_dt=now(),
            payment_provider=BankTransfer(event),
            locale='de',
            gift_cards=[gc1.pk],
        )[0]


@pytest.mark.django_db
def test_giftcard_test_mode_event(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    event.testmode = True
    event.save()
    gc1 = event.organizer.issued_gift_cards.create(currency='EUR', testmode=False)
    gc1.transactions.create(value=12)
    with pytest.raises(OrderError):
        _create_order(
            event,
            email='dummy@example.org',
            positions=[cp1],
            now_dt=now(),
            payment_provider=BankTransfer(event),
            locale='de',
            gift_cards=[gc1.pk],
        )[0]


@pytest.mark.django_db
def test_giftcard_swap(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        issue_giftcard=True,
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    gc1 = event.organizer.issued_gift_cards.create(currency='EUR', testmode=False)
    gc1.transactions.create(value=12)
    with pytest.raises(OrderError):
        _create_order(
            event,
            email='dummy@example.org',
            positions=[cp1],
            now_dt=now(),
            payment_provider=BankTransfer(event),
            locale='de',
            gift_cards=[gc1.pk],
        )[0]


@pytest.mark.django_db
def test_issue_when_paid_and_changed(event):
    ticket = Item.objects.create(
        event=event,
        name='Early-bird ticket',
        issue_giftcard=True,
        default_price=Decimal('23.00'),
        admission=True,
    )
    cp1 = CartPosition.objects.create(
        product=ticket,
        price=23,
        expires=now() + timedelta(days=1),
        event=event,
        cart_id='123',
    )
    q = event.quotas.create(size=None, name='foo')
    q.products.add(ticket)
    order = _create_order(
        event,
        email='dummy@example.org',
        positions=[cp1],
        now_dt=now(),
        payment_provider=BankTransfer(event),
        locale='de',
        gift_cards=[],
    )[0]
    op = order.positions.first()
    assert not op.issued_gift_cards.exists()
    order.payments.first().confirm()
    gc1 = op.issued_gift_cards.get()
    assert gc1.value == op.price
    op.refresh_from_db()
    assert op.secret == gc1.secret

    ocm = OrderChangeManager(order)
    ocm.add_position(ticket, None, Decimal('12.00'))
    ocm.commit()
    order.payments.create(provider='manual', amount=order.pending_sum).confirm()

    assert op.issued_gift_cards.count() == 1
    op2 = order.positions.last()
    gc2 = op2.issued_gift_cards.get()
    assert gc2.value == op2.price


class OrderReactivateTest(TestCase):
    def setUp(self):
        super().setUp()
        self.o = Organizer.objects.create(name='Dummy', slug='dummy')
        with scope(organizer=self.o):
            self.event = Event.objects.create(
                organizer=self.o,
                name='Dummy',
                slug='dummy',
                date_from=now(),
                plugins='tests.tickets.testdummy',
            )
            self.order = Order.objects.create(
                code='FOO',
                event=self.event,
                email='dummy@dummy.test',
                status=Order.STATUS_CANCELED,
                locale='en',
                datetime=now(),
                expires=now() + timedelta(days=1),
                cancellation_date=now(),
                total=Decimal('46.00'),
            )
            self.ticket = Item.objects.create(
                event=self.event,
                name='Early-bird ticket',
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.op1 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Peter'},
                positionid=1,
            )
            self.op2 = OrderPosition.objects.create(
                order=self.order,
                product=self.ticket,
                variation=None,
                price=Decimal('23.00'),
                attendee_name_parts={'full_name': 'Dieter'},
                positionid=2,
            )
            self.stalls = Item.objects.create(
                event=self.event,
                name='Stalls',
                default_price=Decimal('23.00'),
                admission=True,
            )
            self.plan = SeatingPlan.objects.create(name='Plan', organizer=self.o, layout='{}')
            self.event.seat_category_mappings.create(layout_category='Stalls', product=self.stalls)
            self.quota = self.event.quotas.create(name='Test', size=None)
            self.quota.products.add(self.stalls)
            self.quota.products.add(self.ticket)
            self.seat_a1 = self.event.seats.create(seat_number='A1', product=self.stalls, seat_guid='A1')
            generate_invoice(self.order)
            djmail.outbox = []

    @classscope(attr='o')
    def test_paid(self):
        self.order.status = Order.STATUS_PAID
        self.order.save()
        with pytest.raises(OrderError):
            reactivate_order(self.order)

    @classscope(attr='o')
    def test_reactivate_unpaid(self):
        e = self.order.expires
        reactivate_order(self.order)
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_PENDING
        assert self.order.all_logentries().last().action_type == 'pretix.event.order.reactivated'
        assert self.order.invoices.count() == 3
        assert self.order.expires > e > now()

    @classscope(attr='o')
    def test_reactivate_paid(self):
        self.order.payments.create(state=OrderPayment.PAYMENT_STATE_CONFIRMED, amount=48.5)
        reactivate_order(self.order)
        self.order.refresh_from_db()
        assert self.order.status == Order.STATUS_PAID
        assert self.order.all_logentries().last().action_type == 'pretix.event.order.reactivated'
        assert self.order.invoices.count() == 3
        assert not self.order.cancellation_date

    @classscope(attr='o')
    def test_reactivate_sold_out(self):
        self.quota.size = 0
        self.quota.save()
        with pytest.raises(OrderError):
            reactivate_order(self.order)

    @classscope(attr='o')
    def test_reactivate_seat_taken(self):
        self.op1.product = self.stalls
        self.op1.seat = self.seat_a1
        self.op1.save()
        self.seat_a1.blocked = True
        self.seat_a1.save()
        with pytest.raises(OrderError):
            reactivate_order(self.order)

    @classscope(attr='o')
    def test_reactivate_voucher_ok(self):
        self.op1.voucher = self.event.vouchers.create(code='FOO', product=self.ticket, redeemed=0, max_usages=1)
        self.op1.save()
        reactivate_order(self.order)
        v = self.op1.voucher
        v.refresh_from_db()
        assert v.redeemed == 1

    @classscope(attr='o')
    def test_reactivate_voucher_budget(self):
        self.op1.voucher = self.event.vouchers.create(code='FOO', product=self.ticket, budget=Decimal('0.00'))
        self.op1.price_before_voucher = self.op1.price * 2
        self.op1.save()
        with pytest.raises(OrderError):
            reactivate_order(self.order)

    @classscope(attr='o')
    def test_reactivate_voucher_used(self):
        self.op1.voucher = self.event.vouchers.create(code='FOO', product=self.ticket, redeemed=1, max_usages=1)
        self.op1.save()
        with pytest.raises(OrderError):
            reactivate_order(self.order)
        v = self.op1.voucher
        v.refresh_from_db()
        assert v.redeemed == 1

    @classscope(attr='o')
    def test_reactivate_gift_card(self):
        gc = self.o.issued_gift_cards.create(currency='EUR', issued_in=self.op1)
        reactivate_order(self.order)
        assert gc.value == 23
