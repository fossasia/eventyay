import csv
import datetime
from decimal import Decimal
from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import patch

from celery.exceptions import Retry
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection
from django.test import Client, RequestFactory, override_settings
from django.utils.timezone import now
from django_scopes import scopes_disabled
from django_scopes.exceptions import ScopeError

from eventyay.base.models import (
    BillingInvoice,
    BillingInvoiceEmail,
    Event,
    LogEntry,
    Order,
    OrderPosition,
    Organizer,
    User,
)
from eventyay.base.services.mail import SendMailException
from eventyay.common.signals import process_scheduled_emails
from eventyay.control.views.admin_sales import SalesOverview
from eventyay.eventyay_common.tasks import (
    billing_invoice_send_email,
    process_auto_billing_charge,
    retry_failed_payment,
)
from eventyay.helpers.stripe_utils import create_payment_intent
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

    def test_export_includes_events_without_dates(self):
        with scopes_disabled():
            self.event.date_from = None
            self.event.save(update_fields=['date_from'])
        response = self.client.get('/admin/sales/', {'export': 'csv'})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode())))
        row = next(row for row in rows[1:] if row[0] == str(self.event.name))
        self.assertEqual(row[5], '')

    @scopes_disabled()
    def test_empty_search_does_not_add_like_predicates(self):
        for invoices in (False, True):
            for query in ('', '   '):
                with self.subTest(invoices=invoices, query=query):
                    view = SalesOverview(invoices=invoices)
                    view.request = RequestFactory().get('/admin/sales/', {'query': query})
                    self.assertNotIn('LIKE', str(view.get_queryset().query))

    def test_status_update_preserves_filters_and_rejects_other_destinations(self):
        destination = '/admin/sales/invoices/?status=n&ordering=id&page=2&query=Community'
        for target in (destination, 'https://evil.example/admin/sales/invoices/',
                       '//evil.example/admin/sales/invoices/', '/admin/users/'):
            with self.subTest(target=target):
                response = self.client.post(
                    f'/admin/sales/invoices/{self.invoice.pk}/status/',
                    {'status': 'n', 'previous_status': 'n', 'next': target},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, destination if target == destination else '/admin/sales/invoices/')

    def test_billing_worker_sends_without_a_tenant_scope(self):
        with scopes_disabled():
            mail = BillingInvoiceEmail.objects.create(
                invoice=self.invoice, delivery_key='initial', recipient='billing@example.com',
                subject='Invoice', body='Invoice content', pdf_base64='cGRm', pdf_filename='invoice.pdf',
            )
        with self.assertRaises(ScopeError):
            BillingInvoiceEmail.objects.exists()
        with (
            patch('eventyay.common.signals.cache.get', return_value=None),
            patch('eventyay.base.services.mail.mail_send_task.run') as send,
        ):
            process_scheduled_emails(sender=None)
        send.assert_called_once()
        with scopes_disabled():
            mail.refresh_from_db()
        self.assertIsNotNone(mail.sent_at)

    def test_missing_invoice_id_does_not_contact_stripe(self):
        with patch('eventyay.helpers.stripe_utils.stripe.PaymentIntent.create') as create:
            for invoice_id in (None, '', 0):
                with self.subTest(invoice_id=invoice_id), self.assertRaises(ValidationError):
                    create_payment_intent(7, 'eur', 'cus_test', 'pm_test', {}, invoice_id)
        create.assert_not_called()

    def test_outbox_timestamp_has_database_index(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, BillingInvoiceEmail._meta.db_table)
        self.assertTrue(any(value['index'] and value['columns'] == ['sent_at'] for value in constraints.values()))

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
        self.assertFalse(self.invoice.automatic_payment_enabled)
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
            self.assertFalse(self.invoice.reminder_enabled)
            self.assertFalse(self.invoice.automatic_payment_enabled)
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
            patch('eventyay.base.services.mail.mail_send_task.run') as send,
        ):
            generator.return_value.generate.return_value = pdf
            billing_invoice_send_email('Invoice', 'Invoice content', self.invoice, billing)
            billing_invoice_send_email('Invoice', 'Invoice content', self.invoice, billing)
            self.assertEqual(BillingInvoiceEmail.objects.filter(invoice=self.invoice).count(), 1)
            send.assert_not_called()
            process_scheduled_emails(sender=None)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.sent_to_email, billing.primary_contact_email)
        self.assertEqual(send.call_args.kwargs['to'], [billing.primary_contact_email])
        self.assertIsNotNone(BillingInvoiceEmail.objects.get(invoice=self.invoice).sent_at)

    @scopes_disabled()
    def test_email_outbox_and_reminder_roll_back_together(self):
        pdf = BytesIO(b'demo pdf')
        pdf.filename = 'invoice.pdf'
        billing = SimpleNamespace(primary_contact_email='new-billing@example.com')
        reminder_date = now()
        with patch('eventyay.eventyay_common.tasks.InvoicePDFGenerator') as generator:
            generator.return_value.generate.return_value = pdf
            with patch.object(BillingInvoice, 'save', side_effect=DatabaseError('write failed')):
                with self.assertRaises(DatabaseError):
                    billing_invoice_send_email(
                        'Reminder',
                        'Reminder content',
                        self.invoice,
                        billing,
                        delivery_key='reminder:test',
                        reminder_date=reminder_date,
                    )
        self.assertFalse(BillingInvoiceEmail.objects.filter(invoice=self.invoice).exists())
        self.invoice.refresh_from_db()
        self.assertIsNone(self.invoice.last_reminder_datetime)

    @scopes_disabled()
    def test_failed_billing_email_does_not_block_later_outbox_entries(self):
        for index, error in enumerate((SendMailException('bad recipient', already_logged=True), Retry('later'))):
            with self.subTest(error=type(error).__name__):
                failed = BillingInvoiceEmail.objects.create(
                    invoice=self.invoice,
                    delivery_key=f'initial:{index}',
                    recipient='bad@example.com',
                    subject='Invoice',
                    body='Invoice content',
                    pdf_base64='cGRm',
                    pdf_filename='invoice.pdf',
                )
                later = BillingInvoiceEmail.objects.create(
                    invoice=self.invoice,
                    delivery_key=f'reminder:{index}',
                    recipient='good@example.com',
                    subject='Reminder',
                    body='Reminder content',
                    pdf_base64='cGRm',
                    pdf_filename='invoice.pdf',
                )

                def send_mail(**kwargs):
                    if kwargs['to'] == ['bad@example.com']:
                        raise error

                with patch('eventyay.base.services.mail.mail_send_task.run', side_effect=send_mail) as send:
                    process_scheduled_emails.__wrapped__(sender=None)
                    process_scheduled_emails.__wrapped__(sender=None)

                failed.refresh_from_db()
                later.refresh_from_db()
                self.assertEqual(failed.failed_attempts, 1)
                self.assertIsNotNone(failed.last_attempt_at)
                self.assertIsNone(failed.sent_at)
                self.assertIsNotNone(later.sent_at)
                self.assertEqual(send.call_count, 2)

    @scopes_disabled()
    def test_paid_invoice_discards_queued_reminder_but_sends_notice(self):
        reminder = BillingInvoiceEmail.objects.create(
            invoice=self.invoice,
            delivery_key='reminder:2026-10-12',
            recipient='billing@example.com',
            subject='Payment reminder',
            body='Please pay',
            pdf_base64='cGRm',
            pdf_filename='invoice.pdf',
        )
        notice = BillingInvoiceEmail.objects.create(
            invoice=self.invoice,
            delivery_key='notice:2026-10',
            recipient='billing@example.com',
            subject='Invoice',
            body='Invoice content',
            pdf_base64='cGRm',
            pdf_filename='invoice.pdf',
        )
        response = self.client.post(
            f'/admin/sales/invoices/{self.invoice.pk}/status/',
            {'status': BillingInvoice.STATUS_PAID, 'previous_status': BillingInvoice.STATUS_PENDING},
        )
        self.assertEqual(response.status_code, 302)

        with patch('eventyay.base.services.mail.mail_send_task.run') as send:
            process_scheduled_emails.__wrapped__(sender=None)

        self.assertFalse(BillingInvoiceEmail.objects.filter(pk=reminder.pk).exists())
        notice.refresh_from_db()
        self.assertIsNotNone(notice.sent_at)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.kwargs['subject'], 'Invoice')

    @scopes_disabled()
    def test_automatic_payment_intent_uses_stable_invoice_idempotency_key(self):
        with (
            patch('eventyay.helpers.stripe_utils.get_stripe_secret_key', return_value='sk_test'),
            patch('eventyay.helpers.stripe_utils.stripe.PaymentIntent.create') as create,
        ):
            create.return_value = SimpleNamespace(id='pi_same')
            for unused in range(2):
                create_payment_intent(
                    7,
                    'eur',
                    'cus_test',
                    'pm_test',
                    {'invoice_id': self.invoice.pk},
                    str(self.invoice.pk),
                )
        self.assertEqual(create.call_count, 2)
        self.assertEqual(
            [call.kwargs['idempotency_key'] for call in create.call_args_list],
            [f'auto-billing-invoice-{self.invoice.pk}'] * 2,
        )

    @scopes_disabled()
    def test_failed_invoice_keeps_unpaid_warning(self):
        self.client.post(
            f'/admin/sales/invoices/{self.invoice.pk}/status/',
            {
                'status': BillingInvoice.STATUS_FAILED,
                'previous_status': BillingInvoice.STATUS_PENDING,
            },
        )
        self.assertTrue(self.organizer.has_unpaid_invoice())

    @scopes_disabled()
    def test_status_only_edit_cannot_schedule_charge_or_retry(self):
        url = f'/admin/sales/invoices/{self.invoice.pk}/status/'
        self.client.post(url, {'status': 'p', 'previous_status': 'n'})
        self.client.post(url, {'status': 'n', 'previous_status': 'p'})
        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.automatic_payment_enabled)
        self.invoice.stripe_payment_intent_id = 'pi_existing'
        self.invoice.reminder_schedule = [now().day]
        self.invoice.save(update_fields=['stripe_payment_intent_id', 'reminder_schedule'])
        with patch('eventyay.eventyay_common.tasks.retry_payment') as retry:
            retry_failed_payment()
        retry.assert_not_called()
        self.invoice.stripe_payment_intent_id = ''
        self.invoice.monthly_bill = (now() - datetime.timedelta(days=20)).date().replace(day=1)
        self.invoice.save(update_fields=['stripe_payment_intent_id', 'monthly_bill'])
        with patch('eventyay.eventyay_common.tasks.process_auto_billing_charge_stripe') as charge:
            process_auto_billing_charge()
        charge.assert_not_called()
