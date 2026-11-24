"""
Ticketing anonymizers replace the identity of buyers and attendees on an order.

Anonymization never deletes records: orders, positions, answers, payments, invoices and check-ins stay,
so reports and statistics still add up. Only the fields that tell *who* someone was are replaced, and
the remaining data stays attached to an anonymous buyer or attendee.

Plugins take part by returning a ``BaseTicketingAnonymizer`` subclass from the
``register_ticketing_anonymizers`` signal.
"""

import json

from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import (
    CachedCombinedTicket,
    CachedTicket,
    Event,
    InvoiceAddress,
    Order,
)
from eventyay.base.models.orders import generate_secret
from eventyay.base.services.invoices import invoice_pdf
from eventyay.base.shredder import shred_log_fields
from eventyay.base.signals import register_ticketing_anonymizers


REDACTED = '█'

ORDER_LOG_IDENTITY_FIELDS = (
    'old_email',
    'new_email',
    'recipient',
    'message',
    'subject',
    'old_phone',
    'new_phone',
    'attendee_name',
    'attendee_name_parts',
    'company',
    'street',
    'zipcode',
    'city',
    'name_parts',
    'name_cached',
)
POSITION_LOG_IDENTITY_FIELDS = frozenset(
    {'attendee_name', 'attendee_email', 'company', 'street', 'zipcode', 'city', 'state', 'country'}
)


class BaseTicketingAnonymizer:
    """
    Base class for anonymizers. Subclasses replace identity data they own for one order at a time and
    must be safe to run more than once on the same order.
    """

    identifier: str
    verbose_name: str

    def __init__(self, event: Event):
        self.event = event

    def __str__(self) -> str:
        return self.identifier

    def anonymize_order(self, order: Order) -> None:
        raise NotImplementedError()  # NOQA


class OrderContactAnonymizer(BaseTicketingAnonymizer):
    identifier = 'order_contact'
    verbose_name = _('Order contact details')

    def anonymize_order(self, order: Order) -> None:
        # Accounts are linked to orders only by email address, so clearing it unlinks the order from
        # every account. Orders without an email address never receive mail.
        order.email = None
        order.phone = None
        order.email_known_to_work = False
        # Rotating the secret stops the order links in earlier emails from opening the order.
        order.secret = generate_secret()
        meta = order.meta_info_data
        if meta and 'contact_form_data' in meta:
            del meta['contact_form_data']
            order.meta_info = json.dumps(meta)
        if order.comment:
            order.comment = 'Anonymized order ticketing data'
        order.save(update_fields=['email', 'phone', 'email_known_to_work', 'secret', 'meta_info', 'comment'])


class AttendeeAnonymizer(BaseTicketingAnonymizer):
    identifier = 'attendees'
    verbose_name = _('Attendee details')

    def anonymize_order(self, order: Order) -> None:
        for position in order.all_positions.all():
            position.attendee_email = None
            position.attendee_name_cached = None
            position.attendee_name_parts = {}
            position.company = None
            position.street = None
            position.zipcode = None
            position.city = None
            position.state = None
            position.country = None
            meta = position.meta_info_data
            if meta and 'attendee_form_data' in meta:
                del meta['attendee_form_data']
                position.meta_info = json.dumps(meta)
            position.save(
                update_fields=[
                    'attendee_email',
                    'attendee_name_cached',
                    'attendee_name_parts',
                    'company',
                    'street',
                    'zipcode',
                    'city',
                    'state',
                    'country',
                    'meta_info',
                ]
            )


class InvoiceAddressAnonymizer(BaseTicketingAnonymizer):
    identifier = 'invoice_address'
    verbose_name = _('Billing address')

    def anonymize_order(self, order: Order) -> None:
        try:
            address = order.invoice_address
        except InvoiceAddress.DoesNotExist:
            return
        address.name_cached = ''
        address.name_parts = {}
        address.company = ''
        address.street = ''
        address.zipcode = ''
        address.city = ''
        address.state = ''
        address.country = ''
        address.country_old = ''
        address.vat_id = ''
        address.vat_id_validated = False
        address.custom_field = ''
        address.internal_reference = ''
        address.beneficiary = ''
        address.save(
            update_fields=[
                'name_cached',
                'name_parts',
                'company',
                'street',
                'zipcode',
                'city',
                'state',
                'country',
                'country_old',
                'vat_id',
                'vat_id_validated',
                'custom_field',
                'internal_reference',
                'beneficiary',
            ]
        )


class InvoiceAnonymizer(BaseTicketingAnonymizer):
    identifier = 'invoices'
    verbose_name = _('Invoice buyer details')

    def anonymize_order(self, order: Order) -> None:
        # The invoice stays with its number, lines, amounts and tax details. Only the buyer is replaced,
        # and the PDF is rendered again from the anonymized data.
        for invoice in order.invoices.prefetch_related('lines'):
            invoice.invoice_to = ''
            invoice.invoice_to_company = None
            invoice.invoice_to_name = None
            invoice.invoice_to_street = None
            invoice.invoice_to_zipcode = None
            invoice.invoice_to_city = None
            invoice.invoice_to_state = None
            invoice.invoice_to_country = None
            invoice.invoice_to_vat_id = None
            invoice.invoice_to_beneficiary = None
            invoice.internal_reference = ''
            invoice.custom_field = None
            for line in invoice.lines.all():
                if not line.attendee_name:
                    continue
                line.description = line.description.replace(line.attendee_name, REDACTED)
                line.attendee_name = None
                line.save(update_fields=['description', 'attendee_name'])
            had_file = bool(invoice.file)
            if had_file:
                invoice.file.delete(save=False)
                invoice.file = None
            invoice.save(
                update_fields=[
                    'invoice_to',
                    'invoice_to_company',
                    'invoice_to_name',
                    'invoice_to_street',
                    'invoice_to_zipcode',
                    'invoice_to_city',
                    'invoice_to_state',
                    'invoice_to_country',
                    'invoice_to_vat_id',
                    'invoice_to_beneficiary',
                    'internal_reference',
                    'custom_field',
                    'file',
                ]
            )
            if had_file and not invoice.shredded:
                invoice_pdf(invoice.pk)


class PaymentInfoAnonymizer(BaseTicketingAnonymizer):
    identifier = 'payment_info'
    verbose_name = _('Payment details')

    def anonymize_order(self, order: Order) -> None:
        # Each payment provider knows which parts of its stored response identify the payer, and keeps
        # transaction IDs, amounts and status for reconciliation.
        providers = self.event.get_payment_providers()
        for obj in (*order.payments.all(), *order.refunds.all()):
            provider = providers.get(obj.provider)
            if provider:
                provider.shred_payment_info(obj)
            elif obj.info and obj.info != '{}':
                obj.info = '{}'
                obj.save(update_fields=['info'])


class CachedTicketAnonymizer(BaseTicketingAnonymizer):
    identifier = 'cached_tickets'
    verbose_name = _('Generated ticket files')

    def anonymize_order(self, order: Order) -> None:
        # Ticket files can print the attendee name. They are generated again on the next download.
        CachedTicket.objects.filter(order_position__order=order).delete()
        CachedCombinedTicket.objects.filter(order=order).delete()


class OrderLogAnonymizer(BaseTicketingAnonymizer):
    identifier = 'order_logs'
    verbose_name = _('Personal data in order logs')

    def anonymize_order(self, order: Order) -> None:
        for entry in order.all_logentries():
            data = entry.parsed_data
            if not isinstance(data, dict):
                continue
            if any(field in data for field in ORDER_LOG_IDENTITY_FIELDS):
                shred_log_fields(entry, banlist=ORDER_LOG_IDENTITY_FIELDS)
                data = entry.parsed_data
            if entry.action_type != 'eventyay.event.order.modified':
                continue
            changed = False
            rows = data.get('data')
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    for key in row:
                        if key == 'attendee_name_parts':
                            row[key] = {'_legacy': REDACTED}
                            changed = True
                        elif key in POSITION_LOG_IDENTITY_FIELDS:
                            row[key] = REDACTED
                            changed = True
            invoice_data = data.get('invoice_data')
            if isinstance(invoice_data, dict):
                for key, value in invoice_data.items():
                    if value:
                        invoice_data[key] = REDACTED
                        changed = True
            if changed:
                entry.data = json.dumps(data)
                entry.shredded = True
                entry.save(update_fields=['data', 'shredded'])


@receiver(register_ticketing_anonymizers, dispatch_uid='ticketing_anonymizers_builtin')
def register_core_anonymizers(sender: Event, **kwargs) -> list[type[BaseTicketingAnonymizer]]:
    return [
        OrderContactAnonymizer,
        AttendeeAnonymizer,
        InvoiceAddressAnonymizer,
        InvoiceAnonymizer,
        PaymentInfoAnonymizer,
        CachedTicketAnonymizer,
        OrderLogAnonymizer,
    ]
