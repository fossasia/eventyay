import csv
import datetime
from decimal import Decimal
from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import BillingInvoice, Event, LogEntry, Order, OrderPosition, Organizer, User
from eventyay.eventyay_common.tasks import billing_invoice_send_email
from tests.tickets.base import SoupTest


@override_settings(SITE_URL='https://testserver')
class AdminSalesTest(SoupTest):
    @scopes_disabled()
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user('sales-admin@example.com', 'dummy', is_staff=True)
        self.client.force_login(self.admin)
        self.admin.staffsession_set.create(date_start=now(), session_key=self.client.session.session_key)
        self.organizer = Organizer.objects.create(name='Community', slug='sales-community')
        self.event = Event.objects.create(
            organizer=self.organizer,
            name='Community Conference',
            slug='sales-conference',
            date_from=now() + datetime.timedelta(days=30),
            live=True,
            currency='EUR',
        )
        self.other = Event.objects.create(
            organizer=Organizer.objects.create(name='Other organizer', slug='sales-other'),
            name='Other event',
            slug='other',
            date_from=now() - datetime.timedelta(days=30),
            currency='USD',
        )
        product = self.event.products.create(name='Admission', default_price=Decimal('10'), admission=True)
        order = Order.objects.create(
            event=self.event, status=Order.STATUS_PAID, total=Decimal('25'), email='buyer@example.com'
        )
        for unused in range(2):
            OrderPosition.objects.create(order=order, product=product, price=Decimal('10'))
        OrderPosition.objects.create(order=order, product=product, price=Decimal('10'), canceled=True)
        pending = Order.objects.create(event=self.event, status=Order.STATUS_PENDING, total=Decimal('10'))
        OrderPosition.objects.create(order=pending, product=product, price=Decimal('10'))
        self.invoice = BillingInvoice.objects.create(
            organizer=self.organizer,
            event=self.event,
            amount=Decimal('100'),
            currency='EUR',
            ticket_fee=Decimal('10'),
            final_ticket_fee=Decimal('7'),
            created_by='system',
            updated_by='system',
            sent_to_email='billing@example.com',
        )

    def test_performance_and_csv_use_paid_orders_without_join_multiplication(self):
        response = self.client.get('/admin/sales/')
        self.assertEqual(response.status_code, 200)
        rows = {row.pk: row for row in response.context['rows']}
        self.assertEqual(rows[self.event.pk].tickets_sold, 2)
        self.assertEqual(rows[self.event.pk].revenue, Decimal('25'))
        self.assertEqual(rows[self.other.pk].revenue, 0)
        self.assertEqual(rows[self.other.pk].sales_status, 'completed')
        response = self.client.get('/admin/sales/', {'query': 'Community', 'export': 'csv'})
        rows = list(csv.reader(StringIO(response.content.decode())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][2:5], ['2', '25.00', 'EUR'])

    def test_invoice_page_and_export_show_discounted_fee(self):
        response = self.client.get('/admin/sales/invoices/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'billing@example.com')
        response = self.client.get('/admin/sales/invoices/', {'query': str(self.invoice.pk), 'export': 'csv'})
        rows = list(csv.reader(StringIO(response.content.decode())))
        self.assertEqual(rows[1][4], '7.00')
        self.assertEqual(rows[1][-1], 'Due')

    def test_filter_sort_and_invalid_ordering(self):
        response = self.client.get('/admin/sales/', {'status': 'active', 'ordering': '-revenue'})
        self.assertEqual([row.pk for row in response.context['rows']], [self.event.pk])
        self.assertEqual(self.client.get('/admin/sales/', {'ordering': 'bad-field'}).status_code, 200)
        response = self.client.get('/admin/sales/invoices/', {'status': 'p'})
        self.assertEqual(response.context['rows'], [])

    @scopes_disabled()
    def test_status_update_is_audited_and_rejects_stale_and_invalid_changes(self):
        url = f'/admin/sales/invoices/{self.invoice.pk}/status/'
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {'status': 'invalid'}).status_code, 400)
        self.assertEqual(self.client.post(url, {'status': 'p', 'previous_status': 'wrong'}).status_code, 409)
        response = self.client.post(url, {'status': 'p', 'previous_status': 'n'})
        self.assertEqual(response.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'p')
        self.assertFalse(self.invoice.reminder_enabled)
        self.assertIsNotNone(self.invoice.paid_datetime)
        log = LogEntry.objects.get(action_type='eventyay.billing.invoice.status_changed')
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.parsed_data, {'old_status': 'n', 'new_status': 'p'})
        self.assertEqual(self.client.post(url, {'status': 'r', 'previous_status': 'n'}).status_code, 409)

    def test_payment_fallback_and_missing_invoice(self):
        response = self.client.get(f'/admin/sales/invoices/{self.invoice.pk}/payment/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment details are not available')
        self.assertEqual(self.client.get('/admin/sales/invoices/999999/payment/').status_code, 404)

    def test_non_admin_and_staff_without_active_session_cannot_access(self):
        user = User.objects.create_user('ordinary@example.com', 'dummy')
        self.client.force_login(user)
        for path in (
            '/admin/sales/',
            '/admin/sales/?export=csv',
            '/admin/sales/invoices/',
            f'/admin/sales/invoices/{self.invoice.pk}/payment/',
        ):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(
            self.client.post(f'/admin/sales/invoices/{self.invoice.pk}/status/', {'status': 'p'}).status_code, 403
        )
        self.client.force_login(self.admin)
        self.admin.staffsession_set.all().delete()
        response = self.client.get('/admin/sales/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/sudo', response.url)

    def test_status_update_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.admin.staffsession_set.create(date_start=now(), session_key=client.session.session_key)
        self.assertEqual(
            client.post(f'/admin/sales/invoices/{self.invoice.pk}/status/', {'status': 'p'}).status_code, 403
        )

    @scopes_disabled()
    def test_csv_escapes_formulas_and_exports_all_pages(self):
        self.event.name = '=HYPERLINK("example")'
        self.event.save()
        for index in range(26):
            Event.objects.create(
                organizer=self.organizer, name=f'Extra {index}', slug=f'extra-{index}', date_from=now()
            )
        response = self.client.get('/admin/sales/')
        self.assertEqual(len(response.context['rows']), 25)
        self.assertTrue(response.context['is_paginated'])
        response = self.client.get('/admin/sales/', {'export': 'csv', 'page': '2', 'ordering': 'name'})
        rows = list(csv.reader(StringIO(response.content.decode())))
        self.assertEqual(len(rows), 29)
        self.assertTrue(any(row[0].startswith("'=") for row in rows))

    def test_due_date_uses_calendar_month(self):
        self.invoice.created_at = datetime.datetime(2026, 1, 31, tzinfo=datetime.UTC)
        self.assertEqual(self.invoice.due_date, datetime.datetime(2026, 2, 28, tzinfo=datetime.UTC))

    def test_malformed_search_and_sort_do_not_raise(self):
        for query in ('²', '9' * 500):
            self.assertEqual(self.client.get('/admin/sales/invoices/', {'query': query}).status_code, 200)
        for ordering in ('--revenue', '-', 'event__name__bad'):
            self.assertEqual(self.client.get('/admin/sales/', {'ordering': ordering}).status_code, 200)

    @scopes_disabled()
    def test_all_invoice_statuses_and_noop_updates(self):
        previous = 'n'
        for status in ('p', 'g', 'r', 'f', 's', 'c', 'e', 'n'):
            response = self.client.post(
                f'/admin/sales/invoices/{self.invoice.pk}/status/',
                {
                    'status': status,
                    'previous_status': previous,
                },
            )
            self.assertEqual(response.status_code, 302)
            self.invoice.refresh_from_db()
            self.assertEqual(self.invoice.status, status)
            self.assertEqual(self.invoice.reminder_enabled, status == 'n')
            previous = status
        count = LogEntry.objects.filter(action_type='eventyay.billing.invoice.status_changed').count()
        self.client.post(f'/admin/sales/invoices/{self.invoice.pk}/status/', {'status': 'n', 'previous_status': 'n'})
        self.assertEqual(LogEntry.objects.filter(action_type='eventyay.billing.invoice.status_changed').count(), count)

    @scopes_disabled()
    def test_invoice_email_records_queued_recipient(self):
        pdf = BytesIO(b'demo pdf')
        pdf.filename = 'invoice.pdf'
        billing = SimpleNamespace(primary_contact_email='new-billing@example.com')
        with (
            patch('eventyay.eventyay_common.tasks.InvoicePDFGenerator') as generator,
            patch('eventyay.eventyay_common.tasks.mail_send_task.apply_async') as enqueue,
        ):
            generator.return_value.generate.return_value = pdf
            billing_invoice_send_email('Invoice', 'Invoice content', self.invoice, billing)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.sent_to_email, billing.primary_contact_email)
        self.assertEqual(enqueue.call_args.kwargs['kwargs']['to'], [billing.primary_contact_email])
