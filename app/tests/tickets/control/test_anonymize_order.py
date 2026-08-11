from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
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
        """The anonymize_order service should scrub PII from order/positions/invoice_address/answers when event has ended."""
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
