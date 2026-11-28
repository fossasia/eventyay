"""Queued-mail placeholder resolution for specific-attendee compose (#7038/#7039).

These live under tests/stable so Video & Backend CI actually runs them
(tests/tickets is collect-only in CI).
"""

from datetime import timedelta

import pytest
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import Order, OrderPosition, Product
from eventyay.plugins.sendmail.forms import EmailQueueEditForm
from eventyay.plugins.sendmail.models import (
    ComposingFor,
    EmailQueue,
    EmailQueueToUser,
    resolve_queued_mail_text,
)


@pytest.fixture
def item(event):
    with scope(organizer=event.organizer):
        return Product.objects.create(name='Test item', event=event, default_price=13)


@pytest.fixture
def order(event, item):
    with scope(organizer=event.organizer):
        return Order.objects.create(
            event=event,
            status=Order.STATUS_PENDING,
            expires=now() + timedelta(hours=1),
            total=13,
            code='DUMMY',
            email='dummy@dummy.test',
            datetime=now(),
            locale='en',
        )


@pytest.fixture
def pos(order, item):
    with scope(organizer=order.event.organizer):
        return OrderPosition.objects.create(order=order, product=item, price=13)


@pytest.mark.django_db
def test_sent_mail_form_resolves_attendee_name_placeholder(event, order, pos):
    with scope(organizer=event.organizer):
        pos.attendee_name_parts = {'_legacy': 'Rachit Makwana'}
        pos.attendee_email = 'rachit@example.com'
        pos.save()

        queue = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject='Hello {name}',
            message='<p>Hi <span class="tiptap-placeholder-chip" data-variable="name">{name}</span></p>',
            is_draft=False,
            sent_at=now(),
            locale='en',
        )
        EmailQueueToUser.objects.create(
            mail=queue,
            email=pos.attendee_email,
            orders=[order.pk],
            positions=[pos.pk],
        )
        form = EmailQueueEditForm(instance=queue, event=event, read_only=True)

    text = str(form.fields['text'].initial)
    subject = str(form.fields['subject'].initial)
    assert 'Rachit Makwana' in text
    assert '{name}' not in text
    assert 'tiptap-placeholder-chip' not in text
    assert 'Rachit Makwana' in subject


@pytest.mark.django_db
def test_sent_mail_form_blank_name_when_attendee_has_no_name(event, order, pos):
    """Missing attendee/invoice name must resolve to blank, not leave the {name} chip."""
    with scope(organizer=event.organizer):
        pos.attendee_name_parts = {}
        pos.attendee_name_cached = ''
        pos.attendee_email = 'noname@example.com'
        pos.save()
        order.email = 'noname@example.com'
        order.save(update_fields=['email'])

        queue = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject='Hello {name}',
            message='<p>Hi <span class="tiptap-placeholder-chip" data-variable="name">{name}</span>,</p>',
            is_draft=False,
            sent_at=now(),
            locale='en',
        )
        EmailQueueToUser.objects.create(
            mail=queue,
            email=pos.attendee_email,
            orders=[order.pk],
            positions=[pos.pk],
        )
        ctx = queue.placeholder_context()
        form = EmailQueueEditForm(instance=queue, event=event, read_only=True)

    assert ctx is not None
    assert ctx.get('name') == ''
    text = str(form.fields['text'].initial)
    subject = str(form.fields['subject'].initial)
    assert '{name}' not in text
    assert 'tiptap-placeholder-chip' not in text
    assert text == '<p>Hi ,</p>'
    assert subject == 'Hello '
    assert resolve_queued_mail_text(
        '<span class="tiptap-placeholder-chip" data-variable="name">{name}</span>',
        {'name': ''},
    ) == ''


@pytest.mark.django_db
def test_outbox_mail_form_keeps_attendee_name_placeholder(event, order, pos):
    with scope(organizer=event.organizer):
        pos.attendee_name_parts = {'_legacy': 'Rachit Makwana'}
        pos.attendee_email = 'rachit@example.com'
        pos.save()

        queue = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject='Hello {name}',
            message='<p>Hi <span class="tiptap-placeholder-chip" data-variable="name">{name}</span></p>',
            is_draft=False,
            locale='en',
        )
        EmailQueueToUser.objects.create(
            mail=queue,
            email=pos.attendee_email,
            orders=[order.pk],
            positions=[pos.pk],
        )
        form = EmailQueueEditForm(instance=queue, event=event, read_only=False)

    text = str(form.fields['text'].initial)
    subject = str(form.fields['subject'].initial)
    assert '{name}' in text
    assert '{name}' in subject
    assert 'Rachit Makwana' not in text
    assert 'Rachit Makwana' not in subject


def test_resolve_queued_mail_text_keeps_unbalanced_braces():
    assert resolve_queued_mail_text('Hello {name} and {', {'name': 'Ada'}) == 'Hello Ada and {'
    assert (
        resolve_queued_mail_text(
            'Hi {attendee_name} {',
            {'name': 'Ada', 'attendee_name': '{name}'},
        )
        == 'Hi {name} {'
    )
    assert resolve_queued_mail_text('Hello {event.name}', {'event': 'Conf'}) == 'Hello {event.name}'
    assert (
        resolve_queued_mail_text(
            'Hi {name}',
            {'name': '<img src="https://evil.test/x">'},
            escape_text=True,
        )
        == 'Hi &lt;img src=&quot;https://evil.test/x&quot;&gt;'
    )
    assert '<img' in resolve_queued_mail_text(
        'QR {ticket_qr}',
        {'ticket_qr': '<img src="data:image/png;base64,aa">'},
        escape_text=True,
    )


@pytest.mark.django_db
def test_placeholder_context_does_not_record_recipient_errors(event, order, pos, monkeypatch):
    with scope(organizer=event.organizer):
        pos.attendee_email = 'rachit@example.com'
        pos.save()

        queue = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject='Hello',
            message='Hi',
            locale='en',
        )
        recipient = EmailQueueToUser.objects.create(
            mail=queue,
            email=pos.attendee_email,
            orders=[order.pk],
            positions=[pos.pk],
        )

        def fail_context(**kwargs):
            raise ValueError('sample context failure')

        monkeypatch.setattr('eventyay.plugins.sendmail.models.get_email_context', fail_context)
        assert queue.placeholder_context(recipient) is None
        recipient.refresh_from_db()
        assert recipient.error is None


@pytest.mark.django_db
def test_queued_mail_uses_position_matching_recipient_email(event, order, item):
    with scope(organizer=event.organizer):
        OrderPosition.objects.create(
            order=order,
            product=item,
            price=13,
            attendee_name_parts={'_legacy': 'First Person'},
            attendee_email='first@example.com',
        )
        second = OrderPosition.objects.create(
            order=order,
            product=item,
            price=13,
            attendee_name_parts={'_legacy': 'Second Person'},
            attendee_email='second@example.com',
        )

        queue = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject='Hello {name}',
            message='Hi {name}',
            is_draft=False,
            sent_at=now(),
            locale='en',
        )
        EmailQueueToUser.objects.create(
            mail=queue,
            email=second.attendee_email,
            orders=[order.pk],
            positions=list(
                OrderPosition.objects.filter(order=order).order_by('pk').values_list('pk', flat=True)
            ),
        )
        form = EmailQueueEditForm(instance=queue, event=event, read_only=True)

    subject = str(form.fields['subject'].initial)
    assert 'Second Person' in subject
    assert 'First Person' not in subject


@pytest.mark.django_db
def test_queued_mail_pairs_matching_position_with_its_order(event, item):
    with scope(organizer=event.organizer):
        first_order = Order.objects.create(
            event=event,
            status=Order.STATUS_PENDING,
            expires=now() + timedelta(hours=1),
            total=13,
            code='FIRST',
            email='buyer-a@example.com',
            datetime=now(),
            locale='en',
        )
        second_order = Order.objects.create(
            event=event,
            status=Order.STATUS_PENDING,
            expires=now() + timedelta(hours=1),
            total=13,
            code='SECOND',
            email='buyer-b@example.com',
            datetime=now(),
            locale='en',
        )
        first_pos = OrderPosition.objects.create(
            order=first_order,
            product=item,
            price=13,
            attendee_name_parts={'_legacy': 'First Person'},
            attendee_email='other@example.com',
        )
        second_pos = OrderPosition.objects.create(
            order=second_order,
            product=item,
            price=13,
            attendee_name_parts={'_legacy': 'Second Person'},
            attendee_email='shared@example.com',
        )

        queue = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject='Hello {name} {code}',
            message='Hi {name}',
            is_draft=False,
            sent_at=now(),
            locale='en',
        )
        EmailQueueToUser.objects.create(
            mail=queue,
            email=second_pos.attendee_email,
            orders=[first_order.pk],
            positions=[first_pos.pk, second_pos.pk],
        )
        form = EmailQueueEditForm(instance=queue, event=event, read_only=True)

    subject = str(form.fields['subject'].initial)
    assert 'Second Person' in subject
    assert 'SECOND' in subject
    assert 'First Person' not in subject
    assert 'FIRST' not in subject


@pytest.mark.django_db
def test_placeholder_context_uses_override_email(event, order, item):
    with scope(organizer=event.organizer):
        first = OrderPosition.objects.create(
            order=order,
            product=item,
            price=13,
            attendee_name_parts={'_legacy': 'First Person'},
            attendee_email='first@example.com',
        )
        second = OrderPosition.objects.create(
            order=order,
            product=item,
            price=13,
            attendee_name_parts={'_legacy': 'Second Person'},
            attendee_email='second@example.com',
        )

        queue = EmailQueue.objects.create(
            event=event,
            composing_for=ComposingFor.ATTENDEES,
            subject='Hello {name}',
            message='Hi {name}',
            locale='en',
        )
        recipient = EmailQueueToUser.objects.create(
            mail=queue,
            email=second.attendee_email,
            orders=[order.pk],
            positions=[first.pk, second.pk],
        )
        ctx = queue.placeholder_context(recipient, email=first.attendee_email)

    assert ctx['name'] == 'First Person'
