import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Event,
    Invoice,
    InvoiceAddress,
    InvoiceLine,
    Order,
    OrderPayment,
    OrderPosition,
    Organizer,
    Product,
    Question,
    QuestionAnswer,
    QuestionOption,
    SubEvent,
    Team,
    User,
)
from eventyay.base.services.anonymize import anonymize_order, is_order_event_ended
from tests.tickets.base import SoupTest


@override_settings(DEBUG=True)
class OrderAnonymizeTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.orga = Organizer.objects.create(name='Dummy', slug='dummy')
        self.event = Event.objects.create(
            organizer=self.orga,
            name='Dummy Event',
            slug='dummy',
            date_from=now() - timedelta(days=2),
            date_to=now() - timedelta(days=1),
            plugins='eventyay.plugins.banktransfer',
        )
        self.user = User.objects.create_user('orga@example.com', 'test')
        self.team = Team.objects.create(
            organizer=self.orga,
            name='Admin Team',
            all_events=True,
            can_change_orders=True,
        )
        self.team.members.add(self.user)
        self.client.login(email='orga@example.com', password='test')

        self.customer = User.objects.create_user('customer@example.com', 'test')
        self.item = Product.objects.create(event=self.event, name='Ticket', default_price=Decimal('23.00'))
        self.order = Order.objects.create(
            code='ANON1',
            event=self.event,
            email='customer@example.com',
            phone='+1234567890',
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now() + timedelta(days=1),
            total=Decimal('23.00'),
            comment='Customer note',
        )
        self.position = OrderPosition.objects.create(
            order=self.order,
            product=self.item,
            price=Decimal('23.00'),
            attendee_name_cached='John Doe',
            attendee_email='customer@example.com',
            company='ACME Corp',
            street='123 Main St',
            city='Tech City',
            zipcode='12345',
            country='DE',
        )
        self.invoice_addr = InvoiceAddress.objects.create(
            order=self.order,
            name_cached='John Doe',
            company='ACME Corp',
            street='123 Main St',
            city='Tech City',
            zipcode='12345',
            country='DE',
            vat_id='EU123456789',
            custom_field='TAX12345',
        )
        self.question = Question.objects.create(
            event=self.event,
            question='Dietary requirements',
            type=Question.TYPE_STRING,
        )
        self.qa = QuestionAnswer.objects.create(
            orderposition=self.position,
            question=self.question,
            answer='Vegan',
        )
        self.choice_question = Question.objects.create(
            event=self.event,
            question='T-Shirt size',
            type=Question.TYPE_CHOICE,
        )
        self.choice_opt = QuestionOption.objects.create(
            question=self.choice_question,
            answer='L',
            identifier='L',
        )
        self.qa_choice = QuestionAnswer.objects.create(
            orderposition=self.position,
            question=self.choice_question,
            answer='L',
        )
        self.qa_choice.options.add(self.choice_opt)

        self.invoice = Invoice.objects.create(
            order=self.order,
            event=self.event,
            organizer=self.orga,
            prefix='INV',
            invoice_no='1001',
            full_invoice_no='INV-1001',
            date=now().date(),
            invoice_to='John Doe\nACME Corp\n123 Main St',
            introductory_text='Hello John',
            additional_text='Thank you',
            payment_provider_text='Paid via bank transfer',
        )
        self.invoice.file.save('invoice.pdf', ContentFile(b'fake pdf data'))
        self.invoice_line = InvoiceLine.objects.create(
            invoice=self.invoice,
            description='Ticket for John Doe',
            gross_value=Decimal('23.00'),
            tax_value=Decimal('0.00'),
            tax_rate=Decimal('0.00'),
        )

        self.payment = self.order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CONFIRMED,
            amount=Decimal('23.00'),
            payment_date=now(),
            provider='banktransfer',
            info=json.dumps({'payer': 'John Doe', 'iban': 'DE1234567890', 'reference': 'REF123'}),
        )

        self.order.log_action(
            'eventyay.event.order.modified',
            data={
                'data': [{
                    'positionid': self.position.positionid,
                    'attendee_name': 'John Doe',
                    'attendee_email': 'customer@example.com',
                    'company': 'ACME Corp',
                }],
                'invoice_data': {
                    'name_cached': 'John Doe',
                    'street': '123 Main St',
                },
            },
            user=self.user,
        )

    def test_anonymize_order_service(self):
        """The anonymize_order service should scrub all PII from order, positions, invoices, answers, payments, and logs."""
        with scopes_disabled():
            anonymize_order(self.order, user=self.user)
            self.order.refresh_from_db()
            self.position.refresh_from_db()
            self.invoice_addr.refresh_from_db()
            self.qa.refresh_from_db()
            self.qa_choice.refresh_from_db()
            self.customer.refresh_from_db()
            self.invoice.refresh_from_db()
            self.invoice_line.refresh_from_db()
            self.payment.refresh_from_db()

            # User account is unaffected
            assert self.customer.is_active is True
            assert self.customer.email == 'customer@example.com'

            # Order fields
            assert self.order.email == 'anonymized-order-ANON1@eventyay.local'
            assert self.order.phone is None
            assert self.order.comment == 'Anonymized order ticketing data'
            # Financial fields are preserved
            assert self.order.total == Decimal('23.00')
            assert self.order.status == Order.STATUS_PAID

            # Attendee fields on OrderPosition
            assert self.position.attendee_email == f'anonymized-ticket-{self.position.pk}@eventyay.local'
            assert self.position.attendee_name_cached is None
            assert self.position.attendee_name_parts == {}
            assert self.position.company is None
            assert self.position.street is None
            assert self.position.city is None
            assert self.position.country is None

            # InvoiceAddress fields
            assert self.invoice_addr.name_cached == ''
            assert self.invoice_addr.company == ''
            assert self.invoice_addr.street == ''
            assert self.invoice_addr.vat_id == ''
            assert self.invoice_addr.custom_field == ''
            assert str(self.invoice_addr.country) == ''
            assert self.invoice_addr.name_parts == {}

            # QuestionAnswer content & choice options cleared
            assert self.qa.answer == '█'
            assert self.qa_choice.answer == '█'
            assert self.qa_choice.options.count() == 0

            # Invoices shredded
            assert self.invoice.shredded is True
            assert bool(self.invoice.file) is False
            assert self.invoice.invoice_to == '█'
            assert self.invoice.introductory_text == '█'
            assert self.invoice.additional_text == '█'
            assert self.invoice.payment_provider_text == '█'
            assert self.invoice.invoice_no == '1001'
            assert self.invoice_line.gross_value == Decimal('23.00')

            # Payment info shredded
            assert self.payment.info_data.get('_shredded') is True
            assert self.payment.info_data.get('payer') == '█'

            # Audit log entry written & modified log redacted
            assert self.order.all_logentries().filter(action_type='eventyay.event.order.anonymized').exists()
            mod_log = self.order.all_logentries().filter(action_type='eventyay.event.order.modified').first()
            assert mod_log.shredded is True
            assert mod_log.parsed_data['data'][0]['attendee_name'] == '█'
            assert mod_log.parsed_data['data'][0]['attendee_email'] == '█'
            assert mod_log.parsed_data['invoice_data']['name_cached'] == '█'

    def test_anonymize_order_view_get_and_post(self):
        """GET shows the confirmation page; POST triggers anonymization and redirects when event has ended."""
        url = f'/control/event/{self.orga.slug}/{self.event.slug}/orders/ANON1/anonymize'

        response = self.client.get(url)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'pretixcontrol/order/anonymize.html')

        response = self.client.post(url, follow=True)
        assert response.status_code == 200

        with scopes_disabled():
            self.order.refresh_from_db()
            assert self.order.email == 'anonymized-order-ANON1@eventyay.local'

    def test_order_detail_view_toolbar_button(self):
        """Order detail view toolbar displays enabled link when event ended and disabled button with tooltip when ongoing."""
        url = f'/control/event/{self.orga.slug}/{self.event.slug}/orders/ANON1/'

        # Event is ended (date_to was yesterday): link is active
        response = self.client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Anonymize ticket data' in content
        assert f'/orders/ANON1/anonymize' in content

        # Future event: button is disabled with tooltip
        with scopes_disabled():
            self.event.date_from = now() + timedelta(days=1)
            self.event.date_to = now() + timedelta(days=2)
            self.event.save()

        response = self.client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Anonymize ticket data' in content
        assert 'disabled' in content
        assert 'Order ticketing data cannot be anonymized before the associated event has ended.' in content

    def test_anonymize_order_before_event_end_fails(self):
        """Order anonymization before event end should raise ValidationError and block UI control view."""
        with scopes_disabled():
            self.event.date_from = now() + timedelta(days=1)
            self.event.date_to = now() + timedelta(days=2)
            self.event.save()

            assert is_order_event_ended(self.order) is False

            with pytest.raises(ValidationError):
                anonymize_order(self.order, user=self.user)

        url = f'/control/event/{self.orga.slug}/{self.event.slug}/orders/ANON1/anonymize'

        # GET redirects to order page with error
        response = self.client.get(url, follow=True)
        assert response.status_code == 200
        assert 'cannot be anonymized before the associated event has ended' in response.content.decode()

        # POST redirects to order page with error without modifying order
        response = self.client.post(url, follow=True)
        assert response.status_code == 200
        assert 'cannot be anonymized before the associated event has ended' in response.content.decode()

        with scopes_disabled():
            self.order.refresh_from_db()
            assert self.order.email == 'customer@example.com'

    def test_anonymize_order_future_event_without_date_to_fails(self):
        """An event whose start date is in the future and has no date_to should not be treated as ended."""
        with scopes_disabled():
            self.event.has_subevents = True
            self.event.save()

            se = SubEvent.objects.create(
                event=self.event,
                name='Future Sub Event',
                date_from=now() + timedelta(days=1),
                date_to=None,
            )
            self.position.subevent = se
            self.position.save()

            assert is_order_event_ended(self.order) is False

            with pytest.raises(ValidationError):
                anonymize_order(self.order, user=self.user)

    def test_anonymize_order_subevent_not_ended_fails(self):
        """If event has subevents and position subevent has not ended, anonymization fails."""
        with scopes_disabled():
            self.event.has_subevents = True
            self.event.save()

            se = SubEvent.objects.create(
                event=self.event,
                name='Sub Event',
                date_from=now() + timedelta(days=1),
                date_to=now() + timedelta(days=2),
            )
            self.position.subevent = se
            self.position.save()

            assert is_order_event_ended(self.order) is False

            with pytest.raises(ValidationError):
                anonymize_order(self.order, user=self.user)
