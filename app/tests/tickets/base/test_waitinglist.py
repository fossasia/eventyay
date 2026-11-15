import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.apps import apps
from django.core import mail as djmail
from django.db import OperationalError, connection, connections, transaction
from django.test import TestCase
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import (
    Event,
    Product as Item,
    ProductVariation as ItemVariation,
    Organizer,
    Quota,
    Voucher,
    WaitingListEntry,
)
from eventyay.base.models.waitinglist import WaitingListException
from eventyay.base.services.waitinglist import (
    assign_automatically,
    process_waitinglist,
)
from tests.testutils.scope import classscope


@pytest.mark.django_db
@pytest.mark.parametrize('quota_size', [None, 0, 1])
@pytest.mark.parametrize('with_variation', [False, True])
def test_send_voucher_quota_capacity(quota_size, with_variation, monkeypatch):
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
        if quota_size == 0:
            with pytest.raises(WaitingListException):
                entry.send_voucher()
            entry.refresh_from_db()
            assert entry.voucher_id is None
            assert not sent
        else:
            entry.send_voucher()
            entry.refresh_from_db()
            assert entry.voucher.product == product
            assert entry.voucher.variation == variation
            assert entry.voucher.block_quota
            assert sent == [entry.email]


@pytest.fixture(params=[False, True])
def unlimited_waitinglist_entry(db, request, monkeypatch):
    """Prepare unlimited capacity and record mail for a product or variation."""
    organizer = Organizer.objects.create(name='Assignment checks', slug='assignment-checks')
    event = Event.objects.create(
        organizer=organizer, name='Assignment checks', slug='assignment-checks',
        date_from=now() + timedelta(days=1), live=True,
    )
    with scope(event=event, organizer=organizer):
        product = Item.objects.create(event=event, name='Ticket', default_price=23)
        quota = Quota.objects.create(event=event, name='Tickets', size=None)
        variation = ItemVariation.objects.create(product=product, value='Standard') if request.param else None
        if variation:
            quota.variations.add(variation)
        else:
            quota.products.add(product)
        entry = WaitingListEntry.objects.create(
            event=event, product=product, variation=variation, email='waiting@example.test',
        )
    sent = []
    monkeypatch.setattr('eventyay.base.models.waitinglist.mail', lambda *args, **kwargs: sent.append(args[0]))
    return entry, quota, sent


def test_send_voucher_rejects_stale_assigned_entry(unlimited_waitinglist_entry):
    """A stale entry must not create or email a second usable voucher."""
    entry, _, sent = unlimited_waitinglist_entry
    with scope(event=entry.event, organizer=entry.event.organizer):
        stale = WaitingListEntry.objects.get(pk=entry.pk)
        entry.send_voucher()
        with pytest.raises(WaitingListException, match='already been sent'):
            stale.send_voucher()
        assert Voucher.objects.count() == 1
        assert len(sent) == 1
        stale.refresh_from_db()
        assert stale.voucher_id == entry.voucher_id


@pytest.mark.parametrize('cached_capacity', [None, sys.maxsize])
def test_send_voucher_rechecks_reduced_quota(unlimited_waitinglist_entry, cached_capacity):
    """A cached unlimited result must not bypass a newly exhausted finite quota."""
    entry, quota, sent = unlimited_waitinglist_entry
    with scope(event=entry.event, organizer=entry.event.organizer):
        cache = {}
        entry.send_voucher(quota_cache=cache)
        other = WaitingListEntry.objects.create(
            event=entry.event, product=entry.product, variation=entry.variation, email='other@example.test',
        )
        stale = WaitingListEntry.objects.select_related('product', 'variation').prefetch_related(
            'product__quotas', 'variation__quotas',
        ).get(pk=other.pk)
        quota.size = 1
        quota.save()
        cache[quota.pk] = (Quota.AVAILABILITY_OK, cached_capacity)
        with pytest.raises(WaitingListException, match='currently not available'):
            stale.send_voucher(quota_cache=cache)
        other.refresh_from_db()
        assert other.voucher_id is None
        assert Voucher.objects.count() == 1
        assert len(sent) == 1


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row locks.')
def test_concurrent_waitinglist_assignments_create_one_voucher(unlimited_waitinglist_entry):
    """Two requests that load an unassigned entry must reserve and mail only once."""
    entry, _, sent = unlimited_waitinglist_entry
    event = entry.event
    barrier = Barrier(2)

    def assign():
        """Assign through an independent connection after both requests load the entry."""
        try:
            with scope(event=event, organizer=event.organizer):
                stale = WaitingListEntry.objects.get(pk=entry.pk)
                barrier.wait(timeout=10)
                try:
                    stale.send_voucher()
                except WaitingListException:
                    return 'already assigned'
                return 'sent'
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(assign) for _ in range(2)]
        assert sorted(future.result(timeout=15) for future in futures) == ['already assigned', 'sent']
    with scope(event=event, organizer=event.organizer):
        assert Voucher.objects.count() == 1
        entry.refresh_from_db()
        assert entry.voucher_id is not None
    assert len(sent) == 1


@pytest.mark.django_db(transaction=True, available_apps=[app.name for app in apps.get_app_configs()])
@pytest.mark.skipif(connection.vendor != 'postgresql', reason='Requires PostgreSQL row locks.')
def test_quota_edit_waits_until_voucher_is_reserved(unlimited_waitinglist_entry, monkeypatch):
    """Capacity edits cannot commit between the quota check and voucher reservation."""
    entry, quota, sent = unlimited_waitinglist_entry
    create_voucher = Voucher.objects.create

    def reduce_quota():
        """Attempt a concurrent capacity change with a bounded PostgreSQL lock wait."""
        try:
            with scope(event=entry.event, organizer=entry.event.organizer), transaction.atomic():
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '500ms'")
                Quota.objects.filter(pk=quota.pk).update(size=0)
            return 'changed'
        except OperationalError as error:
            cause = error.__cause__ or error
            return getattr(cause, 'sqlstate', None) or getattr(cause, 'pgcode', None)
        finally:
            connections.close_all()

    def create_after_competing_edit(*args, **kwargs):
        """Check the quota lock at the point immediately before persisting a voucher."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(reduce_quota).result(timeout=10) == '55P03'
        return create_voucher(*args, **kwargs)

    monkeypatch.setattr('eventyay.base.models.waitinglist.Voucher.objects.create', create_after_competing_edit)
    with scope(event=entry.event, organizer=entry.event.organizer):
        entry.send_voucher()
        quota.refresh_from_db()
        assert quota.size is None
        quota.size = 0
        quota.save()
        quota.refresh_from_db()
        assert quota.size == 0
    assert len(sent) == 1


def test_send_voucher_rejects_deleted_entry(unlimited_waitinglist_entry):
    """Deleting an entry while assignment is pending must not resurrect it."""
    entry, _, sent = unlimited_waitinglist_entry
    with scope(event=entry.event, organizer=entry.event.organizer):
        WaitingListEntry.objects.filter(pk=entry.pk).delete()
        with pytest.raises(WaitingListException, match='entry not found'):
            entry.send_voucher()
        assert not Voucher.objects.exists()
        assert not sent


def test_automatic_assignment_rechecks_quota_between_entries(unlimited_waitinglist_entry, monkeypatch):
    """A batch must stop issuing vouchers after unlimited capacity becomes exhausted."""
    entry, quota, sent = unlimited_waitinglist_entry
    original_send = WaitingListEntry.send_voucher
    attempted = []

    def send_then_reduce(self, *args, **kwargs):
        """Reduce capacity between the first successful assignment and the next entry."""
        attempted.append(self.pk)
        original_send(self, *args, **kwargs)
        if self.pk == entry.pk:
            quota.size = 1
            quota.save()

    with scope(event=entry.event, organizer=entry.event.organizer):
        other = WaitingListEntry.objects.create(
            event=entry.event, product=entry.product, variation=entry.variation, email='other@example.test',
        )
        monkeypatch.setattr(WaitingListEntry, 'send_voucher', send_then_reduce)
        assert assign_automatically.apply(args=(entry.event_id,), throw=True).get() == 1
        assert attempted == [entry.pk, other.pk]
        other.refresh_from_db()
        assert other.voucher_id is None
        assert Voucher.objects.count() == 1
        assert len(sent) == 1


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
