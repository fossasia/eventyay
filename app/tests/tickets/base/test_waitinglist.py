from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from datetime import timedelta
from threading import Event as ThreadEvent
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core import mail as djmail
from django.db import OperationalError, connection, connections, transaction
from django.test import TestCase
from django.utils.timezone import now
from django_scopes import scope
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as APIValidationError

from eventyay.api.serializers.waitinglist import WaitingListSerializer
from eventyay.api.views.waitinglist import WaitingListViewSet
from eventyay.base.models import (
    Event,
    Product as Item,
    ProductVariation as ItemVariation,
    Organizer,
    Quota,
    SubEvent,
    Voucher,
    WaitingListEntry,
)
from eventyay.base.models.waitinglist import WaitingListBusy, WaitingListException
from eventyay.base.services.locking import LockTimeoutException
from eventyay.base.services.waitinglist import (
    assign_automatically,
    process_waitinglist,
)
from tests.testutils.scope import classscope


@pytest.mark.django_db
@pytest.mark.parametrize('quota_size', [None, 0, 1])
@pytest.mark.parametrize('with_variation', [False, True])
@pytest.mark.parametrize('release_failure', [None, 'lock', 'database timeout', 'database connection'])
def test_send_voucher_quota_capacity(quota_size, with_variation, release_failure, monkeypatch):
    """Unlimited capacity permits vouchers while exhausted quotas still reject them."""
    organizer = Organizer.objects.create(name='Waiting list', slug='waiting-list')
    event = Event.objects.create(organizer=organizer, name='Waiting list', slug='waiting-list', date_from=now())
    with scope(event=event, organizer=organizer):
        product = Item.objects.create(event=event, name='Ticket', default_price=23)
        quota = Quota.objects.create(event=event, name='Tickets', size=quota_size)
        if with_variation:
            variation = ItemVariation.objects.create(product=product, value='Standard')
            quota.variations.add(variation)
        else:
            variation = None
            quota.products.add(product)
        entry = WaitingListEntry.objects.create(
            event=event, product=product, variation=variation, email='waiting@example.com'
        )
        sent = []
        monkeypatch.setattr('eventyay.base.models.waitinglist.mail', lambda *args, **kwargs: sent.append(args[0]))
        if release_failure:
            original_lock = Event.lock
            release_events = []

            @contextmanager
            def failing_release(event):
                """Fail after releasing the booking lock and committing the reservation."""
                with original_lock(event):
                    release_events.append('entered')
                    yield
                assert WaitingListEntry.objects.get(pk=entry.pk).voucher_id is not None
                release_events.append('failed after reservation')
                if release_failure.startswith('database'):
                    cause = OperationalError('database release failed')
                    cause.sqlstate = '55P03' if release_failure == 'database timeout' else '08006'
                    raise OperationalError('database release failed') from cause
                raise LockTimeoutException()

            monkeypatch.setattr(Event, 'lock', failing_release)
        if quota_size == 0:
            with pytest.raises(WaitingListException, match='currently not available'):
                entry.send_voucher()
            entry.refresh_from_db()
            assert entry.voucher_id is None
            assert not Voucher.objects.exists()
            assert not sent
        else:
            second_request = WaitingListEntry.objects.get(pk=entry.pk)
            entry.send_voucher()
            with pytest.raises(WaitingListException, match='already been sent'):
                second_request.send_voucher()
            entry.refresh_from_db()
            assert Voucher.objects.count() == 1
            assert entry.voucher.product == product
            assert entry.voucher.variation == variation
            assert entry.voucher.block_quota
            assert sent == [entry.email]
            if release_failure:
                assert release_events == ['entered', 'failed after reservation', 'entered']


@pytest.mark.django_db
@pytest.mark.parametrize('with_variation', [False, True])
@pytest.mark.parametrize('scenario', ['date', 'capacity', 'busy'])
def test_automatic_assignment_refreshes_capacity_and_retries(with_variation, scenario, monkeypatch):
    """POST date strings, released capacity and temporary contention must permit assignment."""
    organizer = Organizer.objects.create(name='Waiting list', slug='waiting-list')
    event = Event.objects.create(
        organizer=organizer, name='Waiting list', slug='waiting-list',
        date_from=now() + timedelta(days=1), live=True, has_subevents=True,
    )
    with scope(event=event, organizer=organizer):
        date = SubEvent.objects.create(
            event=event, name='Day', active=True, date_from=event.date_from, date_to=event.date_from,
        )
        product = Item.objects.create(event=event, name='Ticket', default_price=23)
        variation = ItemVariation.objects.create(product=product, value='Standard') if with_variation else None
        quota = Quota.objects.create(
            event=event, subevent=date, name='Tickets', size=0 if scenario == 'capacity' else 2,
        )
        (quota.variations if variation else quota.products).add(variation or product)
        first, second = [
            WaitingListEntry.objects.create(
                event=event, product=product, variation=variation, subevent=date,
                email=f'waiting{i}@example.test', priority=2 - i,
            ) for i in range(2)
        ]
        other_date = SubEvent.objects.create(
            event=event, name='Other day', active=True, date_from=event.date_from, date_to=event.date_from,
        )
        other_quota = Quota.objects.create(event=event, subevent=other_date, name='Other date', size=2)
        (other_quota.variations if variation else other_quota.products).add(variation or product)
        unselected = WaitingListEntry.objects.create(
            event=event, product=product, variation=variation, subevent=other_date, email='other@example.test',
        )
        original_send = WaitingListEntry.send_voucher
        attempts, sent = [], []

        def send(entry, *args, **kwargs):
            """Make capacity available after the first rejection, or fail one lock attempt."""
            attempts.append(entry.pk)
            if scenario == 'busy' and len(attempts) == 2:
                raise WaitingListBusy('busy')
            try:
                return original_send(entry, *args, **kwargs)
            finally:
                if scenario == 'capacity' and entry.pk == first.pk:
                    quota.size = 2
                    quota.save(update_fields=['size'])

        monkeypatch.setattr(WaitingListEntry, 'send_voucher', send)
        monkeypatch.setattr('eventyay.base.models.waitinglist.mail', lambda *args, **kwargs: sent.append(args[0]))
        assigned = assign_automatically.apply(
            args=(event.pk, None, str(date.pk)), throw=scenario != 'busy',
        ).get()
        expected = 1 if scenario == 'capacity' else 2
        assert Voucher.objects.count() == len(sent) == expected
        assert assigned == expected
        unselected.refresh_from_db()
        assert unselected.voucher_id is None
        assert attempts == ([first.pk, second.pk, second.pk] if scenario == 'busy' else [first.pk, second.pk])
        if scenario == 'capacity':
            first.refresh_from_db()
            assert first.voucher_id is None


@pytest.mark.django_db
@pytest.mark.parametrize('wrapped', [False, True])
@pytest.mark.parametrize('sqlstate', [
    '08006', '40001', '40P01', '57P03', 'XX000', '08007', None,
])
def test_reservation_database_error_classification(sqlstate, wrapped, monkeypatch):
    """Retry recognized transient failures while preserving unknown and persistent errors."""
    organizer = Organizer.objects.create(name='Waiting list', slug='waiting-list')
    event = Event.objects.create(organizer=organizer, name='Waiting list', slug='waiting-list', date_from=now())
    entry = WaitingListEntry(event=event)
    cause = OperationalError('database error')
    cause.sqlstate = sqlstate
    failure = OperationalError('reservation failed') if wrapped else cause
    if wrapped:
        failure.__cause__ = cause

    def fail(*args, **kwargs):
        """Raise the database error before a reservation can complete."""
        raise failure

    monkeypatch.setattr(Event, 'lock', lambda event: nullcontext())
    monkeypatch.setattr(entry, '_reserve_voucher', fail)
    expected = OperationalError if sqlstate in {'XX000', '08007', None} else WaitingListBusy
    with pytest.raises(expected) as error:
        entry.send_voucher()
    if expected is WaitingListBusy:
        assert error.value.__cause__ is failure
    else:
        assert error.value is failure
    with scope(event=event, organizer=organizer):
        assert not Voucher.objects.exists()


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row locks.')
@pytest.mark.parametrize('locked_row', ['entry', 'product', 'variation'])
def test_reservation_row_contention_returns_busy(locked_row, monkeypatch):
    """Return a retryable conflict instead of waiting while holding the booking lock."""
    organizer = Organizer.objects.create(name='Waiting list', slug='waiting-list')
    event = Event.objects.create(organizer=organizer, name='Waiting list', slug='waiting-list', date_from=now())
    sent = []
    monkeypatch.setattr('eventyay.base.models.waitinglist.mail', lambda *args, **kwargs: sent.append(args[0]))
    with scope(event=event, organizer=organizer):
        product = Item.objects.create(event=event, name='Ticket', default_price=23)
        variation = None
        if locked_row == 'variation':
            variation = ItemVariation.objects.create(product=product, value='Standard')
        quota = Quota.objects.create(event=event, name='Tickets', size=None)
        (quota.variations if variation else quota.products).add(variation or product)
        entry = WaitingListEntry.objects.create(
            event=event, product=product, variation=variation, email='waiting@example.test',
        )
        target = entry if locked_row == 'entry' else variation or product

    def reserve():
        """Attempt the reservation on another connection with a bounded safety timeout."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '2s'")
            with scope(event=event, organizer=organizer):
                candidate = WaitingListEntry.objects.get(pk=entry.pk)
                with connection.execute_wrapper(record_query):
                    with pytest.raises(WaitingListBusy) as error:
                        candidate.send_voucher()
                cause = error.value.__cause__.__cause__ or error.value.__cause__
                code = getattr(cause, 'sqlstate', None) or getattr(cause, 'pgcode', None)
                assert code == '55P03'
                view = WaitingListViewSet()
                view.request = SimpleNamespace(event=event, user=None, auth=None)
                monkeypatch.setattr(view, 'get_object', lambda: candidate)
                response = view.send_voucher()
                assert response.status_code == 409
                assert response['Retry-After'] == '5'
        finally:
            connections.close_all()

    def record_query(execute, sql, params, many, context):
        """Assert the reservation requests nonblocking locks before the safety timeout."""
        if 'FOR UPDATE' in sql:
            assert 'NOWAIT' in sql
        return execute(sql, params, many, context)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with scope(event=event, organizer=organizer), transaction.atomic():
            type(target).objects.select_for_update().get(pk=target.pk)
            pool.submit(reserve).result(timeout=15)
        with scope(event=event, organizer=organizer):
            entry.refresh_from_db()
            assert entry.voucher_id is None
            assert not Voucher.objects.exists()
            assert not sent
            entry.send_voucher()
            entry.refresh_from_db()
            assert entry.voucher_id is not None
            assert Voucher.objects.count() == 1
            assert sent == [entry.email]


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row locks.')
@pytest.mark.parametrize('competing_action', ['assignment', 'product change'])
def test_api_update_revalidates_locked_entry(monkeypatch, competing_action):
    """Recheck a stale PATCH after a competing assignment or product change commits."""
    organizer = Organizer.objects.create(name='Waiting list', slug='waiting-list')
    event = Event.objects.create(organizer=organizer, name='Waiting list', slug='waiting-list', date_from=now())
    ready = ThreadEvent()
    sent = []
    monkeypatch.setattr('eventyay.base.models.waitinglist.mail', lambda *args, **kwargs: sent.append(args[0]))
    with scope(event=event, organizer=organizer):
        product = Item.objects.create(event=event, name='Ticket', default_price=23)
        quota = Quota.objects.create(event=event, name='Tickets', size=None)
        quota.products.add(product)
        entry = WaitingListEntry.objects.create(event=event, product=product, email='original@example.test')
        if competing_action == 'product change':
            first_variant = ItemVariation.objects.create(product=product, value='First')
            second_variant = ItemVariation.objects.create(product=product, value='Second')
            other_product = Item.objects.create(event=event, name='Other ticket', default_price=23)
            other_variant = ItemVariation.objects.create(product=other_product, value='Other')
            quota.variations.add(first_variant, second_variant, other_variant)
            quota.size = 0
            quota.save(update_fields=['size'])
            entry.variation = first_variant
            entry.save()

    def update():
        """Validate the stale PATCH before waiting for the competing transaction."""
        try:
            with scope(event=event, organizer=organizer):
                request = SimpleNamespace(event=event, user=None, auth=None)
                serializer = WaitingListSerializer(
                    WaitingListEntry.objects.get(pk=entry.pk),
                    data=(
                        {'email': 'changed@example.test'} if competing_action == 'assignment'
                        else {'variation': second_variant.pk}
                    ),
                    partial=True,
                    context={'event': event, 'request': request},
                )
                assert serializer.is_valid(), serializer.errors
                view = WaitingListViewSet()
                view.request = request
                view.format_kwarg = None
                ready.set()
                expected = PermissionDenied if competing_action == 'assignment' else APIValidationError
                with pytest.raises(expected):
                    view.perform_update(serializer)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with scope(event=event, organizer=organizer), transaction.atomic():
            WaitingListEntry.objects.select_for_update(of=('self',)).get(pk=entry.pk)
            future = pool.submit(update)
            assert ready.wait(timeout=15)
            if competing_action == 'assignment':
                entry.send_voucher()
            else:
                view = WaitingListViewSet()
                view.request = SimpleNamespace(event=event, user=None, auth=None)
                view.format_kwarg = None
                serializer = view.get_serializer(
                    entry, data={'product': other_product.pk, 'variation': other_variant.pk}, partial=True,
                )
                assert serializer.is_valid(), serializer.errors
                assert serializer.data['product'] == product.pk
                assert serializer.data['variation'] == first_variant.pk
                view.perform_update(serializer)
                assert serializer.data['product'] == other_product.pk
                assert serializer.data['variation'] == other_variant.pk
        future.result(timeout=30)
    with scope(event=event, organizer=organizer):
        entry.refresh_from_db()
        assert entry.email == 'original@example.test'
        if competing_action == 'assignment':
            assert entry.voucher_id is not None
            assert entry.voucher.product_id == product.pk
            assert Voucher.objects.count() == 1
            assert sent == ['original@example.test']
        else:
            assert (entry.product_id, entry.variation_id) == (other_product.pk, other_variant.pk)
            assert not Voucher.objects.exists()
            assert not sent


class WaitingListTestCase(TestCase):
    def setUp(self):
        self.o = Organizer.objects.create(name='Dummy', slug='dummy')
        self.event = Event.objects.create(organizer=self.o, name='Dummy', slug='dummy', date_from=now(), live=True)
        djmail.outbox = []
        with scope(organizer=self.o):
            self.quota = Quota.objects.create(name='Test', size=2, event=self.event)
            self.item1 = Item.objects.create(event=self.event, name='Ticket', default_price=23, admission=True)
            self.item2 = Item.objects.create(event=self.event, name='T-Shirt', default_price=23)
            self.item3 = Item.objects.create(event=self.event, name='Goodie', default_price=23)
            self.var1 = ItemVariation.objects.create(item=self.item2, value='S')
            self.var2 = ItemVariation.objects.create(item=self.item2, value='M')
            self.var3 = ItemVariation.objects.create(item=self.item3, value='Fancy')

    @classscope(attr='o')
    def test_send_unavailable(self):
        self.quota.items.add(self.item1)
        self.quota.size = 0
        self.quota.save()
        wle = WaitingListEntry.objects.create(event=self.event, item=self.item1, email='foo@bar.com')
        with self.assertRaises(WaitingListException):
            wle.send_voucher()

    @classscope(attr='o')
    def test_send_double(self):
        self.quota.variations.add(self.var1)
        self.quota.size = 1
        self.quota.save()
        v = Voucher.objects.create(quota=self.quota, event=self.event, block_quota=True, redeemed=1)
        wle = WaitingListEntry.objects.create(
            event=self.event,
            item=self.item2,
            variation=self.var1,
            email='foo@bar.com',
            voucher=v,
        )
        with self.assertRaises(WaitingListException):
            wle.send_voucher()

    @classscope(attr='o')
    def test_send_variation(self):
        wle = WaitingListEntry.objects.create(
            event=self.event, item=self.item2, variation=self.var1, email='foo@bar.com'
        )
        wle.send_voucher()
        wle.refresh_from_db()

        assert wle.voucher
        assert wle.voucher.item == wle.item
        assert wle.voucher.variation == wle.variation
        assert wle.email in wle.voucher.comment
        assert wle.voucher.block_quota
        assert wle.voucher.max_usages == 1
        assert wle.voucher.event == self.event

        assert len(djmail.outbox) == 1
        assert djmail.outbox[0].to == [wle.email]

    @classscope(attr='o')
    def test_send_custom_validity(self):
        self.event.settings.set('waiting_list_hours', 24)
        wle = WaitingListEntry.objects.create(
            event=self.event, item=self.item2, variation=self.var1, email='foo@bar.com'
        )
        wle.send_voucher()
        wle.refresh_from_db()

        assert 3600 * 23 < (wle.voucher.valid_until - now()).seconds < 3600 * 24

    def test_send_auto(self):
        with scope(organizer=self.o):
            self.quota.variations.add(self.var1)
            self.quota.size = 7
            self.quota.save()
            for i in range(10):
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item2,
                    variation=self.var1,
                    email='foo{}@bar.com'.format(i),
                )
                WaitingListEntry.objects.create(event=self.event, item=self.item1, email='bar{}@bar.com'.format(i))

        assign_automatically.apply(args=(self.event.pk,))
        with scope(organizer=self.o):
            assert WaitingListEntry.objects.filter(voucher__isnull=True).count() == 3
            assert Voucher.objects.count() == 17
            assert sorted(
                list(WaitingListEntry.objects.filter(voucher__isnull=True).values_list('email', flat=True))
            ) == ['foo7@bar.com', 'foo8@bar.com', 'foo9@bar.com']

    def test_send_auto_respect_priority(self):
        with scope(organizer=self.o):
            self.quota.variations.add(self.var1)
            self.quota.size = 7
            self.quota.save()
            for i in range(10):
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item2,
                    variation=self.var1,
                    email='foo{}@bar.com'.format(i),
                    priority=i,
                )
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item1,
                    email='bar{}@bar.com'.format(i),
                    priority=i,
                )

        assign_automatically.apply(args=(self.event.pk,))
        with scope(organizer=self.o):
            assert WaitingListEntry.objects.filter(voucher__isnull=True).count() == 3
            assert Voucher.objects.count() == 17
            assert sorted(
                list(WaitingListEntry.objects.filter(voucher__isnull=True).values_list('email', flat=True))
            ) == ['foo0@bar.com', 'foo1@bar.com', 'foo2@bar.com']

    def test_send_auto_quota_infinite(self):
        with scope(organizer=self.o):
            self.quota.variations.add(self.var1)
            self.quota.size = None
            self.quota.save()
            for i in range(10):
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item2,
                    variation=self.var1,
                    email='foo{}@bar.com'.format(i),
                )
                WaitingListEntry.objects.create(event=self.event, item=self.item1, email='bar{}@bar.com'.format(i))

        assign_automatically.apply(args=(self.event.pk,))
        with scope(organizer=self.o):
            assert WaitingListEntry.objects.filter(voucher__isnull=True).count() == 10
            assert Voucher.objects.count() == 10

    def test_send_periodic_event_over(self):
        self.event.settings.set('waiting_list_enabled', True)
        self.event.settings.set('waiting_list_auto', True)
        self.event.presale_end = now() - timedelta(days=1)
        self.event.save()
        with scope(organizer=self.o):
            for i in range(5):
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item2,
                    variation=self.var1,
                    email='foo{}@bar.com'.format(i),
                )
        process_waitinglist(None)
        with scope(organizer=self.o):
            assert WaitingListEntry.objects.filter(voucher__isnull=True).count() == 5
            assert Voucher.objects.count() == 0
            self.event.presale_end = now() + timedelta(days=1)
            self.event.save()

    def test_send_periodic(self):
        self.event.settings.set('waiting_list_enabled', True)
        self.event.settings.set('waiting_list_auto', True)
        with scope(organizer=self.o):
            for i in range(5):
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item2,
                    variation=self.var1,
                    email='foo{}@bar.com'.format(i),
                )
        process_waitinglist(None)
        with scope(organizer=self.o):
            assert Voucher.objects.count() == 5

    def test_send_periodic_disabled(self):
        self.event.settings.set('waiting_list_enabled', True)
        self.event.settings.set('waiting_list_auto', False)
        with scope(organizer=self.o):
            for i in range(5):
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item2,
                    variation=self.var1,
                    email='foo{}@bar.com'.format(i),
                )
        process_waitinglist(None)
        with scope(organizer=self.o):
            assert WaitingListEntry.objects.filter(voucher__isnull=True).count() == 5
            assert Voucher.objects.count() == 0

    def test_send_periodic_disabled2(self):
        self.event.settings.set('waiting_list_enabled', False)
        self.event.settings.set('waiting_list_auto', True)
        with scope(organizer=self.o):
            for i in range(5):
                WaitingListEntry.objects.create(
                    event=self.event,
                    item=self.item2,
                    variation=self.var1,
                    email='foo{}@bar.com'.format(i),
                )
        process_waitinglist(None)
        with scope(organizer=self.o):
            assert Voucher.objects.count() == 5
