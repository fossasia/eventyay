from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import transaction
from django.db.models.query import QuerySet
from django.test import Client, override_settings
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import (
    Event,
    Product as Item,
    Order,
    OrderPayment,
    OrderPosition,
    OrderRefund,
    Organizer,
    Team,
    User,
)


@pytest.fixture
def env():
    with scopes_disabled():
        o = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=o,
            name='Dummy',
            slug='dummy',
            date_from=now(),
            plugins='eventyay.plugins.banktransfer,eventyay.plugins.stripe',
        )
        user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
        t = Team.objects.create(organizer=o, can_view_orders=True, can_change_orders=True)
        t.members.add(user)
        t.limit_events.add(event)
        order = Order.objects.create(
            code='FOO',
            event=event,
            email='dummy@dummy.test',
            status=Order.STATUS_PENDING,
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=14,
            locale='en',
        )
        order.payments.create(
            amount=order.total,
            provider='banktransfer',
            state=OrderPayment.PAYMENT_STATE_PENDING,
        )
        ticket = Item.objects.create(
            event=event,
            name='Early-bird ticket',
            category=None,
            default_price=23,
            admission=True,
        )
        event.settings.set('attendee_names_asked', True)
        event.settings.set('locales', ['en', 'de'])
        OrderPosition.objects.create(
            order=order,
            product=ticket,
            variation=None,
            price=Decimal('14'),
            attendee_name_parts={'full_name': 'Peter', '_scheme': 'full'},
        )
        return event, user, order, ticket





@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_concurrent_recheck_rejects_over_refund(client, env, monkeypatch):
    """
    Test that when a payment row is locked with select_for_update, the view rechecks
    the available refundable balance against the payment's latest state. If another
    transaction reduced available_amount below the requested amount, the over-refund
    is rejected and no additional refund is created.

    A separate confirmed payment is added so the order-wide balance remains sufficient,
    isolating the payment-specific balance check from the order-wide check.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
        env[2].payments.create(
            order=env[2],
            amount=Decimal('10.00'),
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
        )
    client.login(email='dummy@dummy.dummy', password='dummy')

    original_select_for_update = QuerySet.select_for_update
    locked_models = []

    def mock_select_for_update(self, *args, **kwargs):
        """Intercept select_for_update on OrderPayment and simulate concurrent refund."""
        if self.model is OrderPayment:
            locked_models.append(self.model)
            with scope(event=env[0], organizer=env[0].organizer):
                env[2].refunds.create(
                    order=env[2],
                    payment=p,
                    source=OrderRefund.REFUND_SOURCE_ADMIN,
                    state=OrderRefund.REFUND_STATE_CREATED,
                    amount=Decimal('10.00'),
                    provider=p.provider,
                )
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', mock_select_for_update)

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '14.00',
            'start-mode': 'partial',
            'start-action': 'mark_pending',
            f'refund-{p.pk}': '14.00',
            'perform': 'on',
        },
        follow=True,
    )
    assert OrderPayment in locked_models
    assert b'alert-danger' in resp.content
    assert (
        b'You can not refund more than the amount of a payment that is not yet refunded.'
        in resp.content
    )
    with scope(event=env[0], organizer=env[0].organizer):
        assert list(env[2].refunds.values_list('amount', flat=True)) == [Decimal('10.00')]


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_concurrent_payment_locking_success(client, env, monkeypatch):
    """
    Test that when a valid refund is performed under row locks, Order and OrderPayment
    are locked inside an atomic block and execute_refund runs outside the atomic block.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
    client.login(email='dummy@dummy.dummy', password='dummy')

    atomic_active = []
    original_enter = transaction.Atomic.__enter__
    original_exit = transaction.Atomic.__exit__

    def mock_enter(self):
        atomic_active.append(True)
        return original_enter(self)

    def mock_exit(self, *exc):
        if atomic_active:
            atomic_active.pop()
        return original_exit(self, *exc)

    monkeypatch.setattr(transaction.Atomic, '__enter__', mock_enter)
    monkeypatch.setattr(transaction.Atomic, '__exit__', mock_exit)

    executed_outside_atomic = []
    provider_cls = type(p.payment_provider)
    original_execute_refund = provider_cls.execute_refund

    def mock_execute_refund(self, refund):
        executed_outside_atomic.append(len(atomic_active) == 0)
        return original_execute_refund(self, refund)

    monkeypatch.setattr(provider_cls, 'execute_refund', mock_execute_refund)

    original_select_for_update = QuerySet.select_for_update
    locked_models = []

    def mock_select_for_update(self, *args, **kwargs):
        """Intercept select_for_update to track locked models inside atomic transaction."""
        if self.model in (Order, OrderPayment):
            assert len(atomic_active) > 0
            locked_models.append(self.model)
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', mock_select_for_update)

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '14.00',
            'start-mode': 'partial',
            'start-action': 'mark_pending',
            f'refund-{p.pk}': '14.00',
            'perform': 'on',
        },
        follow=True,
    )
    assert Order in locked_models
    assert OrderPayment in locked_models
    assert executed_outside_atomic and all(executed_outside_atomic)
    assert resp.status_code == 200
    with scope(event=env[0], organizer=env[0].organizer):
        assert env[2].refunds.filter(payment=p, amount=Decimal('14.00')).exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_concurrent_recheck_does_not_leave_giftcard_on_rejection(
    client, env, monkeypatch
):
    """
    Test that when a combined refund (gift card + payment refund) is rejected due to
    concurrent payment balance reduction, no orphan gift card is created on the organizer.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
    client.login(email='dummy@dummy.dummy', password='dummy')

    original_select_for_update = QuerySet.select_for_update
    locked_models = []

    def mock_select_for_update(self, *args, **kwargs):
        """Intercept select_for_update on OrderPayment and simulate concurrent refund."""
        if self.model is OrderPayment:
            locked_models.append(self.model)
            with scope(event=env[0], organizer=env[0].organizer):
                env[2].refunds.create(
                    order=env[2],
                    payment=p,
                    source=OrderRefund.REFUND_SOURCE_ADMIN,
                    state=OrderRefund.REFUND_STATE_CREATED,
                    amount=Decimal('10.00'),
                    provider=p.provider,
                )
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', mock_select_for_update)

    with scope(event=env[0], organizer=env[0].organizer):
        assert env[0].organizer.issued_gift_cards.count() == 0

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '14.00',
            'start-mode': 'full',
            'start-action': 'mark_pending',
            'refund-new-giftcard': '4.00',
            f'refund-{p.pk}': '10.00',
            'perform': 'on',
        },
        follow=True,
    )
    assert OrderPayment in locked_models
    assert b'alert-danger' in resp.content
    assert (
        b'You can not refund more than the amount of a payment that is not yet refunded.'
        in resp.content
    )
    with scope(event=env[0], organizer=env[0].organizer):
        assert env[0].organizer.issued_gift_cards.count() == 0
        assert list(env[2].refunds.values_list('amount', flat=True)) == [Decimal('10.00')]


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_concurrent_recheck_giftcard_created_on_success(client, env, monkeypatch):
    """
    Test that when a combined refund request (gift card and payment refund) passes locked
    validation, the gift card is created within the transaction, saved with the refund,
    and verified to have a linked transaction.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
    client.login(email='dummy@dummy.dummy', password='dummy')

    atomic_active = []
    original_enter = transaction.Atomic.__enter__
    original_exit = transaction.Atomic.__exit__

    def mock_enter(self):
        atomic_active.append(True)
        return original_enter(self)

    def mock_exit(self, *exc):
        if atomic_active:
            atomic_active.pop()
        return original_exit(self, *exc)

    monkeypatch.setattr(transaction.Atomic, '__enter__', mock_enter)
    monkeypatch.setattr(transaction.Atomic, '__exit__', mock_exit)

    executed_outside_atomic = []
    provider_cls = type(p.payment_provider)
    original_execute_refund = provider_cls.execute_refund

    def mock_execute_refund(self, refund):
        executed_outside_atomic.append(len(atomic_active) == 0)
        return original_execute_refund(self, refund)

    monkeypatch.setattr(provider_cls, 'execute_refund', mock_execute_refund)

    original_select_for_update = QuerySet.select_for_update
    locked_models = []

    def mock_select_for_update(self, *args, **kwargs):
        """Intercept select_for_update to track locked models inside atomic transaction."""
        if self.model in (Order, OrderPayment):
            assert len(atomic_active) > 0
            locked_models.append(self.model)
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', mock_select_for_update)

    with scope(event=env[0], organizer=env[0].organizer):
        assert env[0].organizer.issued_gift_cards.count() == 0

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '14.00',
            'start-mode': 'full',
            'start-action': 'mark_pending',
            'refund-new-giftcard': '4.00',
            f'refund-{p.pk}': '10.00',
            'perform': 'on',
        },
        follow=True,
    )
    assert Order in locked_models
    assert OrderPayment in locked_models
    assert executed_outside_atomic and all(executed_outside_atomic)
    assert resp.status_code == 200
    with scope(event=env[0], organizer=env[0].organizer):
        assert env[0].organizer.issued_gift_cards.count() == 1
        card = env[0].organizer.issued_gift_cards.first()
        refund_amounts = sorted(env[2].refunds.values_list('amount', flat=True))
        assert refund_amounts == [Decimal('4.00'), Decimal('10.00')]
        gc_refund = env[2].refunds.get(provider='giftcard')
        assert gc_refund.state == OrderRefund.REFUND_STATE_DONE
        assert gc_refund.amount == Decimal('4.00')
        assert gc_refund.info_data.get('gift_card') == card.pk
        assert card.transactions.filter(refund=gc_refund, value=Decimal('4.00')).exists()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_external_refund_deducted_from_order_wide_balance(client, env, monkeypatch):
    """
    Test that existing refunds in REFUND_STATE_EXTERNAL are deducted from order-wide available
    funds during choose_form validation, preventing paymentless refunds from over-refunding.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
        env[2].refunds.create(
            order=env[2],
            payment=p,
            source=OrderRefund.REFUND_SOURCE_EXTERNAL,
            state=OrderRefund.REFUND_STATE_EXTERNAL,
            amount=Decimal('4.00'),
            provider=p.provider,
        )
    client.login(email='dummy@dummy.dummy', password='dummy')

    original_select_for_update = QuerySet.select_for_update
    locked_models = []

    def mock_select_for_update(self, *args, **kwargs):
        """Intercept select_for_update to track locked models."""
        if self.model in (Order, OrderPayment):
            locked_models.append(self.model)
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', mock_select_for_update)

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '14.00',
            'start-mode': 'partial',
            'start-action': 'mark_pending',
            'refund-manual': '14.00',
            'manual_state': 'done',
            'perform': 'on',
        },
        follow=True,
    )
    assert Order in locked_models
    assert b'alert-danger' in resp.content
    assert (
        b'You can not refund more than the amount of a payment that is not yet refunded.'
        in resp.content
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_full_mode_with_external_refund_succeeds(client, env):
    """
    Test that when an order has an external refund, full refund mode correctly computes
    available balance (payment amount minus external refund) and allows a full refund
    of the remaining balance.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
        env[2].refunds.create(
            order=env[2],
            payment=p,
            source=OrderRefund.REFUND_SOURCE_EXTERNAL,
            state=OrderRefund.REFUND_STATE_EXTERNAL,
            amount=Decimal('4.00'),
            provider=p.provider,
        )
    client.login(email='dummy@dummy.dummy', password='dummy')

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '10.00',
            'start-mode': 'full',
            'start-action': 'mark_pending',
            f'refund-{p.pk}': '10.00',
            'perform': 'on',
        },
        follow=True,
    )
    assert resp.status_code == 200
    with scope(event=env[0], organizer=env[0].organizer):
        refund_amounts = sorted(env[2].refunds.values_list('amount', flat=True))
        assert refund_amounts == [Decimal('4.00'), Decimal('10.00')]


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_concurrent_paymentless_refund_rejects_over_refund(
    client, env, monkeypatch
):
    """
    Test that paymentless refunds serialize under order lock and recheck order-wide
    refundable balance. If another transaction reduced order balance below requested
    amount, the excess paymentless refund is rejected.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
    client.login(email='dummy@dummy.dummy', password='dummy')

    original_select_for_update = QuerySet.select_for_update
    locked_models = []

    def mock_select_for_update(self, *args, **kwargs):
        """Intercept select_for_update on Order and simulate concurrent paymentless refund."""
        if self.model is Order:
            locked_models.append(self.model)
            with scope(event=env[0], organizer=env[0].organizer):
                env[2].refunds.create(
                    order=env[2],
                    payment=None,
                    source=OrderRefund.REFUND_SOURCE_ADMIN,
                    state=OrderRefund.REFUND_STATE_DONE,
                    amount=Decimal('10.00'),
                    provider='manual',
                )
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', mock_select_for_update)

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '14.00',
            'start-mode': 'partial',
            'start-action': 'mark_pending',
            'refund-manual': '14.00',
            'manual_state': 'done',
            'perform': 'on',
        },
        follow=True,
    )
    assert Order in locked_models
    assert b'alert-danger' in resp.content
    assert (
        b'You can not refund more than the amount of a payment that is not yet refunded.'
        in resp.content
    )
    with scope(event=env[0], organizer=env[0].organizer):
        assert list(env[2].refunds.values_list('amount', flat=True)) == [Decimal('10.00')]


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_refund_paid_order_concurrent_unconfirmed_payment_rejects_refund(client, env, monkeypatch):
    """
    Test that if a payment transitions to a non-confirmed state (e.g. CANCELED) before
    lock acquisition, the view rejects the refund under lock and displays the standard error.

    A separate confirmed payment is added so the order-wide balance remains sufficient,
    isolating the payment state check from the order-wide balance check.
    """
    with scope(event=env[0], organizer=env[0].organizer):
        p = env[2].payments.last()
        p.info_data = {'payer': 'Test User', 'iban': 'DE27520521540534534466'}
        p.save()
        p.confirm()
        env[2].payments.create(
            order=env[2],
            amount=Decimal('14.00'),
            provider='manual',
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
        )
    client.login(email='dummy@dummy.dummy', password='dummy')

    original_select_for_update = QuerySet.select_for_update
    locked_models = []

    def mock_select_for_update(self, *args, **kwargs):
        """Intercept select_for_update on OrderPayment and change state to CANCELED."""
        if self.model is OrderPayment:
            locked_models.append(self.model)
            with scope(event=env[0], organizer=env[0].organizer):
                p.state = OrderPayment.PAYMENT_STATE_CANCELED
                p.save(update_fields=['state'])
        return original_select_for_update(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, 'select_for_update', mock_select_for_update)

    resp = client.post(
        '/control/event/dummy/dummy/orders/FOO/refund',
        {
            'start-partial_amount': '14.00',
            'start-mode': 'partial',
            'start-action': 'mark_pending',
            f'refund-{p.pk}': '14.00',
            'perform': 'on',
        },
        follow=True,
    )
    assert OrderPayment in locked_models
    assert b'alert-danger' in resp.content
    assert (
        b'You can not refund more than the amount of a payment that is not yet refunded.'
        in resp.content
    )
    with scope(event=env[0], organizer=env[0].organizer):
        assert env[2].refunds.count() == 0
