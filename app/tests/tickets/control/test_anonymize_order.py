from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import TestCase, override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Event,
    InvoiceAddress,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Question,
    QuestionAnswer,
    Team,
    User,
)
from eventyay.base.services.anonymize import anonymize_order
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
            date_from=now(),
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
        )
        self.invoice_addr = InvoiceAddress.objects.create(
            order=self.order,
            name_cached='John Doe',
            company='ACME Corp',
            street='123 Main St',
            city='Tech City',
            zipcode='12345',
            vat_id='EU123456789',
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

    def test_anonymize_order_service(self):
        """The anonymize_order service should scrub PII from order/positions/invoice_address/answers."""
        with scopes_disabled():
            anonymize_order(self.order, user=self.user)
            self.order.refresh_from_db()
            self.position.refresh_from_db()
            self.invoice_addr.refresh_from_db()
            self.qa.refresh_from_db()
            self.customer.refresh_from_db()

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

            # InvoiceAddress fields
            assert self.invoice_addr.name_cached == ''
            assert self.invoice_addr.company == ''
            assert self.invoice_addr.street == ''
            assert self.invoice_addr.vat_id == ''

            # QuestionAnswer content
            assert self.qa.answer == '█'

            # Audit log entry written
            assert self.order.all_logentries().filter(action_type='eventyay.event.order.anonymized').exists()

    def test_anonymize_order_view_get_and_post(self):
        """GET shows the confirmation page; POST triggers anonymization and redirects."""
        url = f'/control/event/{self.orga.slug}/{self.event.slug}/orders/ANON1/anonymize'

        response = self.client.get(url)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'pretixcontrol/order/anonymize.html')

        response = self.client.post(url, follow=True)
        assert response.status_code == 200

        with scopes_disabled():
            self.order.refresh_from_db()
            assert self.order.email == 'anonymized-order-ANON1@eventyay.local'
