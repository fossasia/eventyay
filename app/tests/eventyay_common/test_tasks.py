import datetime as real_datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import BillingInvoice
from eventyay.eventyay_common.tasks import (
    check_billing_status_for_warning,
    retry_failed_payment,
)


class FakeDatetime(real_datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return real_datetime.datetime(2026, 2, 28, tzinfo=real_datetime.UTC)


@pytest.fixture
@scopes_disabled()
def billing_invoice_factory(organizer, event):
    def _factory(**kwargs):
        defaults = dict(
            organizer=organizer,
            event=event,
            status=BillingInvoice.STATUS_PENDING,
            amount=Decimal('10.00'),
            currency='EUR',
            ticket_fee=Decimal('10.00'),
            final_ticket_fee=Decimal('10.00'),
            created_by='test',
            updated_by='test',
            monthly_bill=timezone.now().date(),
            stripe_payment_intent_id='pi_test',
        )
        defaults.update(kwargs)

        with mock.patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = FakeDatetime.now()
            return BillingInvoice.objects.create(**defaults)

    return _factory


@pytest.mark.django_db
@mock.patch('eventyay.eventyay_common.tasks.retry_payment')
@mock.patch('eventyay.eventyay_common.tasks.datetime', FakeDatetime)
def test_retry_failed_payment_short_month(mock_retry_payment, billing_invoice_factory):
    # invoice 1: invalid for Feb (Feb 30) - should be skipped cleanly without crashing
    billing_invoice_factory(reminder_schedule=[30])

    # invoice 2: valid for Feb (Feb 15) - should be processed
    invoice2 = billing_invoice_factory(reminder_schedule=[15])

    retry_failed_payment()

    # ensure retry_payment was called for invoice2 but not invoice1
    mock_retry_payment.assert_called_once_with(
        payment_intent_id=invoice2.stripe_payment_intent_id,
        organizer_id=invoice2.organizer_id,
    )


@pytest.mark.django_db
@mock.patch('eventyay.eventyay_common.tasks.billing_invoice_send_email')
@mock.patch('eventyay.eventyay_common.tasks.datetime', FakeDatetime)
def test_check_billing_status_for_warning_short_month(mock_send_email, billing_invoice_factory):
    # invoice 1: invalid for Feb (Feb 30) - should be skipped cleanly without crashing
    billing_invoice_factory(reminder_schedule=[30], reminder_enabled=True)

    # invoice 2: valid for Feb (Feb 15) - should be processed
    invoice2 = billing_invoice_factory(reminder_schedule=[15], reminder_enabled=True)

    check_billing_status_for_warning()

    # ensure warning email was sent for invoice2 but not invoice1
    assert mock_send_email.call_count == 1

    # call_args is (args, kwargs), where args is a tuple.
    # billing_invoice_send_email signature: (mail_subject, mail_content, invoice, organizer_billing)
    called_invoice = mock_send_email.call_args[0][2]
    assert called_invoice == invoice2
