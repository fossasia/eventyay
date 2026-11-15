from contextlib import contextmanager
from datetime import timedelta

import pytest
from django.core import mail as djmail
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
from eventyay.base.services.locking import LockTimeoutException
from eventyay.base.services.waitinglist import (
    assign_automatically,
    process_waitinglist,
)
from tests.testutils.scope import classscope


@pytest.mark.django_db
@pytest.mark.parametrize('quota_size', [None, 0, 1])
@pytest.mark.parametrize('with_variation', [False, True])
@pytest.mark.parametrize('release_failure', [False, True])
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

            @contextmanager
            def failing_release(event):
                """Fail after releasing the booking lock and committing the reservation."""
                with original_lock(event):
                    yield
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
