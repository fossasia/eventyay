import json
import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.base.anonymizer import anonymize_line_description
from eventyay.base.models import (
    Checkin,
    CheckinList,
    Invoice,
    InvoiceAddress,
    InvoiceLine,
    Order,
    OrderPayment,
    OrderPosition,
    Product,
    Question,
    QuestionAnswer,
    QuestionOption,
    Team,
    User,
)
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.base.services.anonymize import anonymize_order
from eventyay.base.services.mail import mail, mail_send_task
from eventyay.base.services.orders import OrderChangeManager
from eventyay.helpers.anonymization import is_anonymized_email
from eventyay.plugins.banktransfer.models import BankImportJob, BankTransaction
from eventyay.plugins.banktransfer.payment import BankTransfer


ATTENDEE = 'John Doe'
EMAIL = 'customer@example.com'
ORDER_PLACEHOLDER = re.compile(r'^order\.[a-z0-9]{10}@eventyay\.invalid$')
ATTENDEE_PLACEHOLDER = re.compile(r'^attendee\.[a-z0-9]{10}@eventyay\.invalid$')


@pytest.fixture
def past_event(event):
    event.date_from = now() - timedelta(days=3)
    event.date_to = now() - timedelta(days=2)
    event.plugins = 'eventyay.plugins.banktransfer'
    event.save()
    return event


@pytest.fixture
def customer(db):
    return User.objects.create_user(EMAIL, 'customer')


@pytest.fixture
def data(past_event, customer):
    with scope(organizer=past_event.organizer, event=past_event):
        product = Product.objects.create(event=past_event, name='Ticket', default_price=Decimal('23.00'))
        order = Order.objects.create(
            code='ANON1',
            event=past_event,
            email=EMAIL,
            phone='+491234567890',
            status=Order.STATUS_PAID,
            datetime=now() - timedelta(days=10),
            expires=now() - timedelta(days=5),
            total=Decimal('23.00'),
            comment='Called about the invoice',
            meta_info=json.dumps({'contact_form_data': {'email': EMAIL}, 'other': 'kept'}),
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=Decimal('23.00'),
            attendee_name_parts={'_scheme': 'full', 'full_name': ATTENDEE},
            attendee_email=EMAIL,
            company='ACME Corp',
            street='123 Main St',
            zipcode='12345',
            city='Tech City',
            country='DE',
            meta_info=json.dumps({'attendee_form_data': {'name': ATTENDEE}}),
        )
        address = InvoiceAddress.objects.create(
            order=order,
            name_parts={'_scheme': 'full', 'full_name': ATTENDEE},
            company='ACME Corp',
            street='123 Main St',
            zipcode='12345',
            city='Tech City',
            country='DE',
            vat_id='DE123456789',
            custom_field='PO-42',
        )
        text_question = Question.objects.create(event=past_event, question='Dietary needs', type=Question.TYPE_STRING)
        text_answer = QuestionAnswer.objects.create(orderposition=position, question=text_question, answer='Vegan')
        choice_question = Question.objects.create(event=past_event, question='Size', type=Question.TYPE_CHOICE)
        option = QuestionOption.objects.create(question=choice_question, answer='L', identifier='L')
        choice_answer = QuestionAnswer.objects.create(orderposition=position, question=choice_question, answer='L')
        choice_answer.options.add(option)
        invoice = Invoice.objects.create(
            order=order,
            event=past_event,
            organizer=past_event.organizer,
            prefix='INV-',
            invoice_no='00001',
            full_invoice_no='INV-00001',
            date=now().date(),
            invoice_to=f'ACME Corp\n{ATTENDEE}\n123 Main St',
            invoice_to_name=ATTENDEE,
            invoice_to_company='ACME Corp',
            invoice_to_street='123 Main St',
            invoice_to_zipcode='12345',
            invoice_to_city='Tech City',
            invoice_to_country='DE',
            invoice_to_vat_id='DE123456789',
            introductory_text='Thanks for your order',
        )
        invoice.file.save('invoice.pdf', ContentFile(b'%PDF fake'))
        line = InvoiceLine.objects.create(
            invoice=invoice,
            description=f'Ticket<br />Attendee: {ATTENDEE}',
            attendee_name=ATTENDEE,
            gross_value=Decimal('23.00'),
            tax_value=Decimal('0.00'),
            tax_rate=Decimal('0.00'),
        )
        payment = order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('23.00'),
            payment_date=now() - timedelta(days=9),
            provider='banktransfer',
            info=json.dumps({'payer': ATTENDEE, 'iban': 'DE89370400440532013000', 'reference': 'ANON1'}),
        )
        checkin_list = CheckinList.objects.create(event=past_event, name='Entrance')
        Checkin.objects.create(position=position, list=checkin_list)
        order.log_action(
            'eventyay.event.order.modified',
            data={
                'data': [
                    {
                        'position': position.pk,
                        'attendee_name': ATTENDEE,
                        'attendee_email': EMAIL,
                        'company': 'ACME Corp',
                        f'question_{text_question.pk}': 'Vegan',
                    }
                ],
                'invoice_data': {'name_cached': ATTENDEE, 'street': '123 Main St'},
            },
        )
        order.log_action(
            'eventyay.event.order.email.order_paid',
            data={'recipient': EMAIL, 'subject': 'Paid', 'message': f'Hello {ATTENDEE}, see /order/ANON1/secret/'},
        )
        order.log_action('eventyay.event.order.paid', data={'provider': 'banktransfer'})
    with scope(organizer=past_event.organizer, event=past_event):
        job = BankImportJob.objects.create(event=past_event)
        transaction = BankTransaction.objects.create(
            event=past_event,
            import_job=job,
            state=BankTransaction.STATE_VALID,
            message='',
            checksum='abc',
            payer=ATTENDEE,
            reference='ANON1 thanks',
            amount=Decimal('23.00'),
            date='2026-01-01',
            iban='DE89370400440532013000',
            bic='COBADEFFXXX',
            order=order,
        )
    return {
        'event': past_event,
        'order': order,
        'position': position,
        'address': address,
        'text_answer': text_answer,
        'choice_answer': choice_answer,
        'invoice': invoice,
        'line': line,
        'payment': payment,
        'transaction': transaction,
    }


@pytest.fixture
def rendered_invoices(monkeypatch):
    calls = []
    monkeypatch.setattr('eventyay.base.anonymizer.invoice_pdf', calls.append)
    return calls


def event_scope(event):
    return scope(organizer=event.organizer, event=event)


def refresh(event, *objects):
    with event_scope(event):
        for obj in objects:
            obj.refresh_from_db()


@pytest.mark.django_db
def test_identity_is_removed_from_order_and_attendees(data, rendered_invoices):
    order, position, address = data['order'], data['position'], data['address']
    old_secret, old_web_secret = order.secret, position.web_secret
    anonymize_order(order)
    refresh(data['event'], order, position, address)

    assert ORDER_PLACEHOLDER.match(order.email)
    assert order.phone is None
    assert order.secret != old_secret
    assert position.web_secret != old_web_secret
    assert order.meta_info_data == {'other': 'kept'}
    assert order.comment == 'Anonymized order ticketing data'

    assert position.attendee_name == 'Anonymized'
    assert position.attendee_name_cached == 'Anonymized'
    assert ATTENDEE_PLACEHOLDER.match(position.attendee_email)
    assert position.company is None
    assert position.street is None
    assert position.zipcode is None
    assert position.city is None
    assert not position.country
    assert 'attendee_form_data' not in (position.meta_info_data or {})

    assert address.name_cached == 'Anonymized'
    assert address.name_parts == {'_legacy': 'Anonymized'}
    assert address.company == ''
    assert address.street == ''
    assert address.vat_id == ''
    assert address.custom_field == ''


@pytest.mark.django_db
def test_records_and_answers_are_kept(data, rendered_invoices):
    order, position = data['order'], data['position']
    anonymize_order(order)
    refresh(data['event'], order, position, data['text_answer'], data['choice_answer'])

    assert order.status == Order.STATUS_PAID
    assert order.total == Decimal('23.00')
    with event_scope(data['event']):
        assert order.all_positions.count() == 1
        assert position.price == Decimal('23.00')
        assert position.checkins.count() == 1
        assert order.payments.get().amount == Decimal('23.00')
    assert data['text_answer'].answer == 'Vegan'
    assert data['choice_answer'].answer == 'L'
    with event_scope(data['event']):
        assert list(data['choice_answer'].options.values_list('identifier', flat=True)) == ['L']


@pytest.mark.django_db
def test_invoice_keeps_number_and_amounts_but_loses_buyer(data, rendered_invoices):
    invoice, line = data['invoice'], data['line']
    anonymize_order(data['order'])
    refresh(data['event'], invoice, line)

    assert invoice.full_invoice_no == 'INV-00001'
    assert invoice.introductory_text == 'Thanks for your order'
    assert not invoice.shredded
    assert invoice.invoice_to == 'Anonymized'
    assert invoice.invoice_to_name == 'Anonymized'
    assert invoice.invoice_to_company is None
    assert invoice.invoice_to_street is None
    assert invoice.invoice_to_vat_id is None
    assert not invoice.invoice_to_country
    assert line.gross_value == Decimal('23.00')
    assert line.attendee_name == 'Anonymized'
    assert line.description == 'Ticket<br />Attendee: Anonymized'
    assert not invoice.file
    assert rendered_invoices == [invoice.pk]


@pytest.mark.django_db
def test_payment_details_are_reduced(data, rendered_invoices):
    payment, transaction = data['payment'], data['transaction']
    anonymize_order(data['order'])
    refresh(data['event'], payment, transaction)

    assert payment.info_data['payer'] == '█'
    assert payment.info_data['reference'] == '█'
    assert payment.info_data['iban'] == '█'
    assert payment.info_data['_shredded'] is True
    assert transaction.payer == '█'
    assert transaction.reference == '█'
    assert transaction.iban == ''
    assert transaction.bic == ''
    assert transaction.amount == Decimal('23.00')
    assert transaction.checksum == 'abc'
    assert transaction.state == BankTransaction.STATE_VALID


@pytest.mark.django_db
def test_logs_lose_identity_but_keep_answers(data, rendered_invoices):
    order = data['order']
    anonymize_order(order)

    with event_scope(data['event']):
        modified = order.all_logentries().get(action_type='eventyay.event.order.modified')
        email = order.all_logentries().get(action_type='eventyay.event.order.email.order_paid')
        paid = order.all_logentries().get(action_type='eventyay.event.order.paid')
        assert order.all_logentries().filter(action_type='eventyay.event.order.anonymized').exists()

    row = modified.parsed_data['data'][0]
    assert modified.shredded
    assert row['attendee_name'] == '█'
    assert row['attendee_email'] == '█'
    assert row['company'] == '█'
    assert row[f'question_{data["text_answer"].question_id}'] == 'Vegan'
    assert modified.parsed_data['invoice_data'] == {'name_cached': '█', 'street': '█'}

    assert email.shredded
    assert email.parsed_data['recipient'] == '█'
    assert email.parsed_data['message'] == '█'
    assert email.parsed_data['subject'] == '█'

    assert not paid.shredded
    assert paid.parsed_data == {'provider': 'banktransfer'}


@pytest.mark.django_db
def test_order_is_unlinked_from_account_and_gets_no_mail(data, customer, rendered_invoices, mailoutbox):
    order = data['order']
    anonymize_order(order)
    refresh(data['event'], order, customer)

    assert customer.is_active
    assert customer.email == EMAIL
    # Accounts find their orders across all events, so this lookup is deliberately not scoped to one event.
    with scopes_disabled():
        assert not Order.objects.filter(email__iexact=customer.email).exists()
        assert not OrderPosition.objects.filter(attendee_email__iexact=customer.email).exists()
    with event_scope(data['event']):
        order.send_mail('Subject', LazyI18nString('Body'), {})
        data['position'].refresh_from_db()
        data['position'].send_mail('Subject', 'Body', {})
    assert mailoutbox == []


@pytest.mark.django_db
def test_running_twice_is_safe(data, rendered_invoices):
    order, position, line = data['order'], data['position'], data['line']
    anonymize_order(order)
    refresh(data['event'], order, position)
    placeholders = (order.email, position.attendee_email)
    anonymize_order(order)
    refresh(data['event'], order, position, line, data['text_answer'])
    assert (order.email, position.attendee_email) == placeholders
    assert line.description == 'Ticket<br />Attendee: Anonymized'
    assert data['text_answer'].answer == 'Vegan'


@pytest.mark.django_db
def test_placeholders_are_unique_per_order(data, rendered_invoices):
    order = data['order']
    with event_scope(data['event']):
        other = Order.objects.create(
            code='ANON2',
            event=order.event,
            email=EMAIL,
            status=Order.STATUS_PAID,
            datetime=order.datetime,
            expires=order.expires,
            total=Decimal('0.00'),
        )
    anonymize_order(order)
    anonymize_order(other)
    refresh(data['event'], order, other)
    assert ORDER_PLACEHOLDER.match(other.email)
    assert order.email != other.email


PLACEHOLDER = 'order.abcdefghij@eventyay.invalid'


def send_task(**kwargs):
    base = {'subject': 'S', 'body': 'B', 'html': None, 'sender': 'x@example.com'}
    return mail_send_task.apply(kwargs={**base, **kwargs})


@pytest.mark.parametrize(
    ('address', 'expected'),
    [
        (PLACEHOLDER, True),
        (' Order.X@EVENTYAY.INVALID ', True),
        ('Anonymous <order.abcdefghij@eventyay.invalid>', True),
        ('"Doe, John" <order.abcdefghij@eventyay.invalid>', True),
        ('Real Person <real@example.com>', False),
        ('real@example.com', False),
        ('x@sub.eventyay.invalid', False),
        ('x@eventyay.invalid.example.com', False),
        ('eventyay.invalid', False),
        ('', False),
        (None, False),
    ],
)
def test_placeholder_detection(address, expected):
    assert is_anonymized_email(address) is expected


@pytest.mark.django_db
def test_mail_is_never_sent_to_placeholder_addresses(mailoutbox):
    mail(PLACEHOLDER, 'Subject', 'Body', {}, sync_send=True)
    mail([PLACEHOLDER, 'Order.X@EVENTYAY.INVALID'], 'Subject', 'Body', {}, sync_send=True)
    mail('Anonymous <order.abcdefghij@eventyay.invalid>', 'Subject', 'Body', {}, sync_send=True)
    assert mailoutbox == []
    send_task(to=[PLACEHOLDER, 'Anonymous <order.klmnopqrst@eventyay.invalid>', 'real@example.com'])
    assert [m.to for m in mailoutbox] == [['real@example.com']]


@pytest.mark.django_db
def test_bcc_recipients_are_filtered_and_bcc_only_mail_is_kept(mailoutbox):
    send_task(to=['real@example.com'], bcc=[PLACEHOLDER, 'copy@example.com'])
    assert (mailoutbox[-1].to, mailoutbox[-1].bcc) == (['real@example.com'], ['copy@example.com'])

    send_task(to=[], bcc=['copy@example.com'])
    assert (mailoutbox[-1].to, mailoutbox[-1].bcc) == ([], ['copy@example.com'])
    assert len(mailoutbox) == 2

    # Addressed only to placeholders: dropped, even though a blind copy would be deliverable.
    send_task(to=[PLACEHOLDER], bcc=['copy@example.com'])
    # Blind copies that are all placeholders and nobody else to send to: dropped.
    send_task(to=[], bcc=[PLACEHOLDER])
    assert len(mailoutbox) == 2


@pytest.mark.django_db
def test_order_mail_goes_to_the_real_attendee_when_only_the_order_email_is_a_placeholder(
    data, rendered_invoices, mailoutbox, django_capture_on_commit_callbacks
):
    order, position, event = data['order'], data['position'], data['event']
    with event_scope(event):
        order.email = PLACEHOLDER
        order.save()
        position.attendee_email = 'attendee@example.com'
        position.save()
        with django_capture_on_commit_callbacks(execute=True):
            order.send_mail('Subject', LazyI18nString('Body'), {}, position=position)
    assert [m.to for m in mailoutbox] == [['attendee@example.com']]


@pytest.mark.django_db
def test_order_mail_is_dropped_when_the_chosen_recipient_is_a_placeholder(
    data, rendered_invoices, mailoutbox, django_capture_on_commit_callbacks
):
    order, position, event = data['order'], data['position'], data['event']
    with event_scope(event):
        order.email = 'buyer@example.com'
        order.save()
        position.attendee_email = PLACEHOLDER
        position.save()
        with django_capture_on_commit_callbacks(execute=True):
            order.send_mail('Subject', LazyI18nString('Body'), {}, position=position)
            order.send_mail('Subject', LazyI18nString('Body'), {})
    assert [m.to for m in mailoutbox] == [['buyer@example.com']]


@pytest.mark.django_db
def test_refused_before_event_end(data, rendered_invoices):
    event, order = data['event'], data['order']
    event.date_from = now() + timedelta(days=1)
    event.date_to = now() + timedelta(days=2)
    event.save()
    with pytest.raises(ValidationError):
        anonymize_order(order)
    refresh(data['event'], order)
    assert order.email == EMAIL


@pytest.mark.django_db
def test_core_and_plugin_anonymizers_are_registered(data):
    identifiers = list(data['event'].get_ticketing_anonymizers())
    assert identifiers[:7] == [
        'order_contact',
        'attendees',
        'invoice_address',
        'invoices',
        'payment_info',
        'cached_tickets',
        'order_logs',
    ]
    assert 'bank_transactions' in identifiers


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_control_view_anonymizes(data, client, rendered_invoices, allow_all_entitlements):
    event, order = data['event'], data['order']
    user = User.objects.create_user('orga@example.com', 'orga')
    team = Team.objects.create(organizer=event.organizer, name='Orga', all_events=True, can_change_orders=True)
    team.members.add(user)
    client.force_login(user)
    url = f'/control/event/{event.organizer.slug}/{event.slug}/orders/{order.code}/anonymize'

    response = client.get(url)
    assert response.status_code == 200
    assert 'answers to ticket questions' in response.content.decode()

    response = client.post(url)
    assert response.status_code == 302
    refresh(data['event'], order)
    assert ORDER_PLACEHOLDER.match(order.email)


@pytest.mark.django_db
def test_api_anonymizes(data, client, rendered_invoices, allow_all_entitlements):
    event, order = data['event'], data['order']
    team = Team.objects.create(organizer=event.organizer, name='API', all_events=True, can_change_orders=True)
    token = TeamAPIToken.objects.create(team=team, name='Token')
    response = client.post(
        f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/orders/{order.code}/anonymize/',
        HTTP_AUTHORIZATION=f'Token {token.token}',
    )
    assert response.status_code == 200
    assert ORDER_PLACEHOLDER.match(response.data['email'])
    assert response.data['phone'] is None


@pytest.mark.parametrize('identity_edit', ['email', 'phone', 'invoice_address', 'comment'])
def test_api_rejects_identity_edits_after_anonymization(event, team, client, identity_edit, allow_all_entitlements):
    with event_scope(event):
        order = Order.objects.create(
            event=event,
            email='anonymous@eventyay.invalid',
            total=0,
            expires=now(),
            is_anonymized=True,
        )
    token = TeamAPIToken.objects.create(team=team, name='Token')
    url = f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/orders/{order.code}/'
    values = {
        'email': 'new@example.com',
        'phone': '+12025550123',
        'invoice_address': {'name': 'New Buyer'},
        'comment': 'New Buyer',
    }
    response = client.patch(
        url,
        {identity_edit: values[identity_edit]},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Token {token.token}',
    )
    assert response.status_code == 400
    assert 'Personal data cannot be edited' in str(response.json())

    response = client.patch(
        url,
        {'checkin_attention': True},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Token {token.token}',
    )
    assert response.status_code == 200
    refresh(event, order)
    assert order.is_anonymized and order.checkin_attention
    assert order.email == 'anonymous@eventyay.invalid' and not order.phone


@override_settings(SITE_URL='https://testserver')
def test_control_rejects_contact_edits_after_anonymization(event, team, authenticated_client, allow_all_entitlements):
    with event_scope(event):
        order = Order.objects.create(
            event=event,
            email='anonymous@eventyay.invalid',
            total=0,
            expires=now(),
            is_anonymized=True,
        )
    url = f'/control/event/{event.organizer.slug}/{event.slug}/orders/{order.code}/contact'
    response = authenticated_client.post(url, {'email': 'new@example.com', 'phone': '+12025550123'})
    assert response.status_code == 302
    refresh(event, order)
    assert order.email == 'anonymous@eventyay.invalid' and not order.phone
    assert order.is_anonymized


@pytest.mark.django_db
def test_api_rejects_attendee_edits_after_anonymization(data, client, rendered_invoices, allow_all_entitlements):
    event, order, position = data['event'], data['order'], data['position']
    anonymize_order(order)
    team = Team.objects.create(organizer=event.organizer, name='API', all_events=True, can_change_orders=True)
    token = TeamAPIToken.objects.create(team=team, name='Token')
    response = client.patch(
        f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/orderpositions/{position.pk}/',
        {'attendee_email': 'new@example.com'},
        content_type='application/json',
        HTTP_AUTHORIZATION=f'Token {token.token}',
    )
    assert response.status_code == 400
    assert 'Personal data cannot be edited' in str(response.json())
    refresh(event, position)
    assert position.attendee_email.endswith('@eventyay.invalid')


def test_line_description_keeps_product_text_that_contains_the_attendee_name():
    description = 'Annual pass<br />Attendee: Ann<br />Dietary needs: Ann is vegan'
    result = anonymize_line_description(description, 'Ann')
    assert result == 'Annual pass<br />Attendee: Anonymized<br />Dietary needs: Anonymized is vegan'
    assert anonymize_line_description('Ann Arbor ticket', 'Ann') == 'Ann Arbor ticket'


@pytest.mark.django_db
def test_invoice_line_keeps_product_name_that_contains_the_attendee_name(data, rendered_invoices):
    line = data['line']
    with event_scope(data['event']):
        line.attendee_name = 'Ann'
        line.description = 'Annual pass<br />Attendee: Ann'
        line.save()
    anonymize_order(data['order'])
    refresh(data['event'], line)
    assert line.description == 'Annual pass<br />Attendee: Anonymized'


@pytest.mark.django_db
def test_stored_invoice_file_is_deleted_only_after_commit(data, rendered_invoices, django_capture_on_commit_callbacks):
    invoice = data['invoice']
    old_name = invoice.file.name
    assert default_storage.exists(old_name)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        anonymize_order(data['order'])
    refresh(data['event'], invoice)
    assert not invoice.file
    assert default_storage.exists(old_name)
    for callback in callbacks:
        callback()
    assert not default_storage.exists(old_name)


@pytest.mark.django_db
def test_invoice_file_survives_a_rollback(data, monkeypatch, django_capture_on_commit_callbacks):
    invoice = data['invoice']
    old_name = invoice.file.name

    def fail(self, obj):
        raise RuntimeError('provider failed')

    monkeypatch.setattr(BankTransfer, 'shred_payment_info', fail)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        with pytest.raises(RuntimeError):
            anonymize_order(data['order'])
    refresh(data['event'], invoice, data['order'])
    # Neither the file deletion nor the PDF task is queued, and nothing was changed.
    assert callbacks == []
    assert invoice.file.name == old_name
    assert default_storage.exists(old_name)
    assert data['order'].email == EMAIL


@pytest.mark.django_db
def test_payment_info_of_an_unavailable_provider_keeps_reconciliation_ids(data, rendered_invoices):
    with event_scope(data['event']):
        gone = data['order'].payments.create(
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('5.00'),
            provider='plugin_that_was_disabled',
            info=json.dumps(
                {'id': 'tx_123', 'status': 'paid', 'amount': '5.00', 'payer_email': EMAIL, 'card': {'last4': '4242'}}
            ),
        )
        opaque = data['order'].payments.create(
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('5.00'),
            provider='plugin_that_was_disabled',
            info='not json: John Doe',
        )
    anonymize_order(data['order'])
    refresh(data['event'], gone, opaque)
    assert json.loads(gone.info) == {
        'id': 'tx_123',
        'status': 'paid',
        'amount': '5.00',
        'payer_email': '█',
        'card': '█',
        '_shredded': True,
    }
    assert opaque.info == '{}'


@pytest.mark.django_db
def test_bank_transactions_are_anonymized_after_the_plugin_was_disabled(data, rendered_invoices):
    event = data['event']
    event.plugins = ''
    event.save()
    assert 'bank_transactions' in event.get_ticketing_anonymizers()
    assert 'banktransfer' not in event.get_payment_providers()
    anonymize_order(data['order'])
    refresh(event, data['transaction'], data['payment'])
    assert data['transaction'].payer == '█'
    assert data['transaction'].iban == ''
    assert data['transaction'].amount == Decimal('23.00')
    assert json.loads(data['payment'].info)['payer'] == '█'
    assert json.loads(data['payment'].info)['iban'] == '█'



@pytest.mark.parametrize('initial,total,difference,expected', [
    (Order.STATUS_PAID, 10, 10, Order.STATUS_PENDING),
    (Order.STATUS_PENDING, 0, -10, Order.STATUS_PAID),
])
def test_price_change_preserves_concurrently_anonymized_identity(event, initial, total, difference, expected):
    with event_scope(event):
        order = Order.objects.create(event=event, email=EMAIL, total=total, status=initial, expires=now())
        manager = OrderChangeManager(order)
        manager._totaldiff = difference
        Order.objects.filter(pk=order.pk).update(email='anonymous@eventyay.invalid', is_anonymized=True)
        manager._check_paid_price_change()
        order.refresh_from_db()
        assert order.status == expected
        assert order.is_anonymized and order.email == 'anonymous@eventyay.invalid'


@override_settings(SITE_URL='https://testserver')
def test_regenerating_secrets_invalidates_cache_after_commit(
    event, team, authenticated_client, allow_all_entitlements, mocker, django_capture_on_commit_callbacks
):
    with event_scope(event):
        order = Order.objects.create(event=event, email=EMAIL, total=0, expires=now())
    invalidate = mocker.patch('eventyay.control.views.orders.tickets.invalidate_cache.apply_async')
    url = f'/control/event/{event.organizer.slug}/{event.slug}/orders/{order.code}/contact'
    with django_capture_on_commit_callbacks(execute=True):
        response = authenticated_client.post(url, {'email': EMAIL, 'regenerate_secrets': 'on'})
        assert response.status_code == 302
        invalidate.assert_not_called()
    invalidate.assert_called_once_with(kwargs={'event': event.pk, 'order': order.pk})
