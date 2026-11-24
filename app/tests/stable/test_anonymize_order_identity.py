import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

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
from eventyay.plugins.banktransfer.models import BankImportJob, BankTransaction


ATTENDEE = 'John Doe'
EMAIL = 'customer@example.com'


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
    with scopes_disabled():
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


def refresh(*objects):
    with scopes_disabled():
        for obj in objects:
            obj.refresh_from_db()


@pytest.mark.django_db
def test_identity_is_removed_from_order_and_attendees(data, rendered_invoices):
    order, position, address = data['order'], data['position'], data['address']
    old_secret = order.secret
    anonymize_order(order)
    refresh(order, position, address)

    assert order.email is None
    assert order.phone is None
    assert order.secret != old_secret
    assert order.meta_info_data == {'other': 'kept'}
    assert order.comment == 'Anonymized order ticketing data'

    assert position.attendee_name is None
    assert position.attendee_name_parts == {}
    assert position.attendee_email is None
    assert position.company is None
    assert position.street is None
    assert position.zipcode is None
    assert position.city is None
    assert not position.country
    assert 'attendee_form_data' not in (position.meta_info_data or {})

    assert address.name_cached == ''
    assert address.name_parts == {}
    assert address.company == ''
    assert address.street == ''
    assert address.vat_id == ''
    assert address.custom_field == ''


@pytest.mark.django_db
def test_records_and_answers_are_kept(data, rendered_invoices):
    order, position = data['order'], data['position']
    anonymize_order(order)
    refresh(order, position, data['text_answer'], data['choice_answer'])

    assert order.status == Order.STATUS_PAID
    assert order.total == Decimal('23.00')
    with scopes_disabled():
        assert order.all_positions.count() == 1
        assert position.price == Decimal('23.00')
        assert position.checkins.count() == 1
        assert order.payments.get().amount == Decimal('23.00')
    assert data['text_answer'].answer == 'Vegan'
    assert data['choice_answer'].answer == 'L'
    with scopes_disabled():
        assert list(data['choice_answer'].options.values_list('identifier', flat=True)) == ['L']


@pytest.mark.django_db
def test_invoice_keeps_number_and_amounts_but_loses_buyer(data, rendered_invoices):
    invoice, line = data['invoice'], data['line']
    anonymize_order(data['order'])
    refresh(invoice, line)

    assert invoice.full_invoice_no == 'INV-00001'
    assert invoice.introductory_text == 'Thanks for your order'
    assert not invoice.shredded
    assert invoice.invoice_to == ''
    assert invoice.invoice_to_name is None
    assert invoice.invoice_to_company is None
    assert invoice.invoice_to_street is None
    assert invoice.invoice_to_vat_id is None
    assert not invoice.invoice_to_country
    assert line.gross_value == Decimal('23.00')
    assert line.attendee_name is None
    assert ATTENDEE not in line.description
    assert line.description.startswith('Ticket<br />Attendee: ')
    assert not invoice.file
    assert rendered_invoices == [invoice.pk]


@pytest.mark.django_db
def test_payment_details_are_reduced(data, rendered_invoices):
    payment, transaction = data['payment'], data['transaction']
    anonymize_order(data['order'])
    refresh(payment, transaction)

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

    with scopes_disabled():
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
    refresh(order, customer)

    assert customer.is_active
    assert customer.email == EMAIL
    with scopes_disabled():
        assert not Order.objects.filter(email__iexact=customer.email).exists()
        assert not OrderPosition.objects.filter(attendee_email__iexact=customer.email).exists()
        order.send_mail('Subject', 'Body', {})
        data['position'].refresh_from_db()
        data['position'].send_mail('Subject', 'Body', {})
    assert mailoutbox == []


@pytest.mark.django_db
def test_running_twice_is_safe(data, rendered_invoices):
    order = data['order']
    anonymize_order(order)
    anonymize_order(order)
    refresh(order, data['text_answer'])
    assert order.email is None
    assert data['text_answer'].answer == 'Vegan'


@pytest.mark.django_db
def test_refused_before_event_end(data, rendered_invoices):
    event, order = data['event'], data['order']
    event.date_from = now() + timedelta(days=1)
    event.date_to = now() + timedelta(days=2)
    event.save()
    with pytest.raises(ValidationError):
        anonymize_order(order)
    refresh(order)
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
    refresh(order)
    assert order.email is None


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
    assert response.data['email'] is None
    assert response.data['phone'] is None
