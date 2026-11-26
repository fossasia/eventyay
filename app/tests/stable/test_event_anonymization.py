from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.anonymizer import OrderContactAnonymizer
from eventyay.base.models import CartPosition, Event, EventAnonymizationRun, Order, Product, User, WaitingListEntry
from eventyay.base.services.event_anonymization import anonymize_event
from eventyay.base.settings import GlobalSettingsObject
from eventyay.helpers.anonymization import is_anonymized_email
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
            meta_info='{"attendee_form_data": "PII"}',
        )
        recipient = EmailQueueToUser.objects.create(
            mail=EmailQueue.objects.create(event=event, bcc='copy@example.org'), email='mail@example.org'
        )
        video = User.objects.create(event=event, token_id='attendee', profile={'name': 'A'})
        protected = User.objects.create(event=event, token_id='owner:orga', profile={'name': 'Owner'})
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
        for record in (waiting, recipient, cart, video, protected, run):
            record.refresh_from_db()
        assert is_anonymized_email(waiting.email) and is_anonymized_email(recipient.email)
        assert recipient.mail.bcc == ''
        assert cart.attendee_email is None and cart.meta_info_data == {}
        assert video.profile == {} and video.token_id is None
        assert protected.profile == {'name': 'Owner'}
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
