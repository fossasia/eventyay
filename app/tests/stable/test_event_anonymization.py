from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.anonymizer import OrderContactAnonymizer
from eventyay.base.models import (
    CartPosition,
    Event,
    EventAnonymizationRun,
    Invoice,
    Order,
    Product,
    Quota,
    User,
    WaitingListEntry,
)
from eventyay.base.models.waitinglist import WaitingListException
from eventyay.base.services.event_anonymization import anonymize_event, flush_pending_file_deletions
from eventyay.base.settings import GlobalSettingsObject
from eventyay.helpers.anonymization import ANONYMIZED_NAME, is_anonymized_email
from eventyay.plugins.sendmail.models import EmailQueue, EmailQueueToUser


def make_order(event, code):
    return Order.objects.create(
        event=event,
        code=code,
        email='buyer@example.org',
        total=23,
        datetime=now(),
        expires=now(),
        status=Order.STATUS_PAID,
    )


def test_event_run_resumes_and_isolates_events(event, monkeypatch):
    event.date_from = event.date_to = now() - timedelta(days=20)
    event.save()
    other = Event.objects.create(organizer=event.organizer, name='Other', slug='other', date_from=event.date_from)
    with scope(event=other, organizer=other.organizer):
        untouched = make_order(other, 'OTHER')
    with scope(event=event, organizer=event.organizer):
        first = make_order(event, 'FIRST')
        second = make_order(event, 'NEXT')
        product = Product.objects.create(event=event, name='Ticket', default_price=23)
        waiting = WaitingListEntry.objects.create(event=event, product=product, email='waiting@example.org')
        cart = CartPosition.objects.create(
            event=event,
            product=product,
            price=23,
            expires=event.date_to,
            attendee_email='cart@example.org',
            job_title='CTO',
            meta_info='{"attendee_form_data": "PII"}',
        )
        recipient = EmailQueueToUser.objects.create(
            mail=EmailQueue.objects.create(event=event, bcc='copy@example.org'), email='mail@example.org'
        )
        video = User.objects.create(
            event=event,
            token_id='attendee',
            client_id='client-123',
            fullname='Alice',
            email='alice@example.org',
            profile={'name': 'A'},
        )
        protected = User.objects.create(
            event=event,
            token_id='owner:orga',
            fullname='Owner',
            email='owner@example.org',
            profile={'name': 'Owner'},
        )
        platform_user = User.objects.create(fullname='Platform', email='platform@example.org')
        original = OrderContactAnonymizer.anonymize_order

        def fail_second(handler, order):
            original(handler, order)
            if order.pk == second.pk:
                raise ValueError('simulated interruption')

        with monkeypatch.context() as patch:
            patch.setattr(OrderContactAnonymizer, 'anonymize_order', fail_second)
            result = anonymize_event.apply(args=(event.pk, 'manual'), throw=False)
            assert result.failed()
        run = EventAnonymizationRun.objects.get(event=event)
        assert run.status == run.Status.FAILED
        assert run.last_order_id == first.pk
        first.refresh_from_db()
        secret = first.secret
        second.refresh_from_db()
        assert second.email == 'buyer@example.org'
        for trigger in ('manual', 'automatic'):
            assert anonymize_event.apply(args=(event.pk, trigger), throw=True).get() == run.pk
        first.refresh_from_db()
        assert first.secret == secret
        second.refresh_from_db()
        assert is_anonymized_email(second.email)
        assert second.total == 23
        for record in (waiting, recipient, cart, video, protected, platform_user, run):
            record.refresh_from_db()
        assert is_anonymized_email(waiting.email) and is_anonymized_email(recipient.email)
        assert recipient.mail.bcc == ''
        assert cart.attendee_email is None and cart.job_title is None and cart.meta_info_data == {}
        assert video.profile == {} and video.token_id is None and video.client_id is None
        assert video.fullname is None and video.email is None
        assert 'Alice' not in str(video) and 'alice@example.org' not in str(video)
        assert protected.profile == {'name': 'Owner'}
        assert protected.fullname == 'Owner' and protected.email == 'owner@example.org'
        assert platform_user.fullname == 'Platform' and platform_user.email == 'platform@example.org'
        assert run.status == run.Status.COMPLETED and run.counts['waiting_list'] == 1
        assert event.logentry_set.filter(action_type='eventyay.event.ticketing_data.anonymized').count() == 1
    with scope(event=other, organizer=other.organizer):
        untouched.refresh_from_db()
        assert untouched.email == 'buyer@example.org'


def test_event_waiting_period(event):
    event.date_to = now() - timedelta(days=13)
    event.date_from = event.date_to - timedelta(days=1)
    event.save()
    with scope(event=event, organizer=event.organizer):
        with pytest.raises(ValidationError):
            anonymize_event.apply(args=(event.pk, 'automatic'), throw=True)
        assert not EventAnonymizationRun.objects.filter(event=event).exists()


def test_last_subevent_controls_waiting_period(event):
    event.has_subevents = True
    event.date_to = event.date_from = now() - timedelta(days=40)
    event.save()
    with scope(event=event, organizer=event.organizer):
        event.subevents.create(name='Final date', date_from=now() - timedelta(days=2))
        with pytest.raises(ValidationError):
            anonymize_event.apply(args=(event.pk, 'manual'), throw=True)
        assert not EventAnonymizationRun.objects.filter(event=event).exists()



def test_configured_minimum(event):
    event.date_from = event.date_to = now() - timedelta(days=18)
    event.save()
    GlobalSettingsObject().settings.set('ticketing_retention_manual_min_days', 21)
    with scope(event=event, organizer=event.organizer):
        with pytest.raises(ValidationError):
            anonymize_event.apply(args=(event.pk, 'manual'), throw=True)
        assert not EventAnonymizationRun.objects.exists()


def test_waiting_list_voucher_and_cart_invalid_meta_cleaned(event):
    event.date_from = event.date_to = now() - timedelta(days=20)
    event.save()
    with scope(event=event, organizer=event.organizer):
        product = Product.objects.create(event=event, name='Ticket', default_price=23)
        quota = Quota.objects.create(event=event, name='Default', size=10)
        quota.products.add(product)
        waiting = WaitingListEntry.objects.create(event=event, product=product, email='waiter@example.org')
        waiting.send_voucher()
        waiting.refresh_from_db()
        assert waiting.voucher is not None
        assert 'waiter@example.org' in waiting.voucher.comment

        null_cart = CartPosition.objects.create(
            event=event,
            product=product,
            price=23,
            expires=event.date_to,
            attendee_email='nullmeta@example.org',
            meta_info='null',
        )
        bad_cart = CartPosition.objects.create(
            event=event,
            product=product,
            price=23,
            expires=event.date_to,
            attendee_email='badmeta@example.org',
            meta_info='{invalid',
        )
        anonymize_event.apply(args=(event.pk, 'manual'), throw=True)

        waiting.refresh_from_db()
        waiting.voucher.refresh_from_db()
        assert is_anonymized_email(waiting.email)
        assert 'waiter@example.org' not in waiting.voucher.comment
        assert ANONYMIZED_NAME in waiting.voucher.comment
        log_entry = event.logentry_set.get(action_type='eventyay.voucher.added.waitinglist')
        assert log_entry.shredded is True
        assert log_entry.parsed_data['email'] == '█'

        null_cart.refresh_from_db()
        bad_cart.refresh_from_db()
        assert null_cart.attendee_email is None and null_cart.meta_info == '{}'
        assert bad_cart.attendee_email is None and bad_cart.meta_info == '{}'


def test_rescan_catches_late_order_below_checkpoint(event):
    event.date_from = event.date_to = now() - timedelta(days=20)
    event.save()
    with scope(event=event, organizer=event.organizer):
        higher_order = make_order(event, 'HIGH')
        run = EventAnonymizationRun.objects.create(
            event=event,
            trigger=EventAnonymizationRun.Trigger.MANUAL,
            last_order_id=higher_order.pk,
        )
        higher_order.is_anonymized = True
        higher_order.save(update_fields=['is_anonymized'])
        original_secret = higher_order.secret

        late_order = Order.objects.create(
            pk=higher_order.pk - 1,
            event=event,
            code='LATE',
            email='late@example.org',
            total=23,
            datetime=now(),
            expires=now(),
            status=Order.STATUS_PAID,
        )
        anonymize_event.apply(args=(event.pk, 'manual'), throw=True)

        late_order.refresh_from_db()
        higher_order.refresh_from_db()
        run.refresh_from_db()
        assert late_order.is_anonymized is True
        assert is_anonymized_email(late_order.email)
        assert higher_order.secret == original_secret
        assert run.status == run.Status.COMPLETED


def test_pending_invoice_pdf_deletion_retries_until_deleted(event, monkeypatch):
    event.date_from = event.date_to = now() - timedelta(days=20)
    event.save()
    with scope(event=event, organizer=event.organizer):
        order = make_order(event, 'INV1')
        invoice = Invoice.objects.create(
            order=order,
            organizer=event.organizer,
            event=event,
            prefix='INV-',
            invoice_no='0001',
            full_invoice_no='INV-0001',
            invoice_from='Org',
            invoice_to='Alice',
            invoice_to_name='Alice',
        )
        invoice.file.save('old-invoice.pdf', ContentFile(b'%PDF-1.4 old'), save=True)
        old_name = invoice.file.name
        storage = Invoice._meta.get_field('file').storage
        assert storage.exists(old_name)

        original_delete = storage.delete
        attempts = {'count': 0}

        def fail_once(name):
            if name == old_name and attempts['count'] == 0:
                attempts['count'] += 1
                raise OSError('storage unavailable')
            return original_delete(name)

        with monkeypatch.context() as patch:
            patch.setattr(storage, 'delete', fail_once)
            result = anonymize_event.apply(args=(event.pk, 'manual'), throw=False)
            assert result.failed()

        run = EventAnonymizationRun.objects.get(event=event)
        assert run.status == run.Status.FAILED
        assert old_name in run.pending_file_deletions
        assert storage.exists(old_name)

        anonymize_event.apply(args=(event.pk, 'manual'), throw=True)
        run.refresh_from_db()
        assert run.status == run.Status.COMPLETED
        assert run.pending_file_deletions == []
        assert not storage.exists(old_name)


def test_file_deletion_preserves_paths_appended_during_flush(event, monkeypatch):
    with scope(event=event):
        run = EventAnonymizationRun.objects.create(
            event=event,
            trigger=EventAnonymizationRun.Trigger.MANUAL,
            pending_file_deletions=['first.pdf'],
        )
        storage = Invoice._meta.get_field('file').storage

        def delete(path):
            assert path == 'first.pdf'
            EventAnonymizationRun.objects.filter(pk=run.pk).update(
                pending_file_deletions=['first.pdf', 'concurrent.pdf'],
            )

        monkeypatch.setattr(storage, 'delete', delete)
        flush_pending_file_deletions(run)

        assert run.pending_file_deletions == ['concurrent.pdf']
        run.refresh_from_db()
        assert run.pending_file_deletions == ['concurrent.pdf']


def test_anonymized_waiting_list_entry_cannot_receive_a_voucher(event):
    event.date_from = event.date_to = now() - timedelta(days=20)
    event.save()
    with scope(event=event, organizer=event.organizer):
        product = Product.objects.create(event=event, name='Ticket', default_price=23)
        Quota.objects.create(event=event, name='All', size=10).products.add(product)
        waiting = WaitingListEntry.objects.create(event=event, product=product, email='waiter@example.org')
        anonymize_event.apply(args=(event.pk, 'manual'), throw=True)
        waiting.refresh_from_db()
        assert is_anonymized_email(waiting.email)
        with pytest.raises(WaitingListException):
            waiting.send_voucher()
        waiting.refresh_from_db()
        assert waiting.voucher is None


def test_stale_waiting_list_entry_cannot_restore_the_original_address(event):
    event.date_from = event.date_to = now() - timedelta(days=20)
    event.save()
    with scope(event=event, organizer=event.organizer):
        product = Product.objects.create(event=event, name='Ticket', default_price=23)
        Quota.objects.create(event=event, name='All', size=10).products.add(product)
        WaitingListEntry.objects.create(event=event, product=product, email='waiter@example.org')
        stale = WaitingListEntry.objects.get()
        anonymize_event.apply(args=(event.pk, 'manual'), throw=True)
        assert stale.email == 'waiter@example.org'
        with pytest.raises(WaitingListException):
            stale.send_voucher()
        stored = WaitingListEntry.objects.get()
        assert is_anonymized_email(stored.email) and stored.voucher is None

