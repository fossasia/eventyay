import json
import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.models import (
    CachedCombinedTicket,
    CachedTicket,
    InvoiceAddress,
    Order,
    QuestionAnswer,
)
from eventyay.base.shredder import shred_log_fields

logger = logging.getLogger(__name__)


def is_order_event_ended(order: Order, current_time=None) -> bool:
    """
    Returns True if the event (and any subevent associated with the order's positions)
    has ended as of current_time (default now()). Returns False if an end time cannot
    be resolved or is in the future.
    """
    if current_time is None:
        current_time = now()

    event = order.event
    if event.has_subevents:
        subevent_ids = [
            sid for sid in order.all_positions.values_list('subevent_id', flat=True).distinct()
            if sid is not None
        ]
        if subevent_ids:
            subevents = event.subevents.filter(id__in=subevent_ids)
            if not subevents.exists():
                return False
            for se in subevents:
                end_time = se.date_to or se.date_from
                if not end_time or current_time <= end_time:
                    return False
            return True

    end_time = event.date_to or event.date_from
    if not end_time or current_time <= end_time:
        return False
    return True


@transaction.atomic
def anonymize_order(order: Order, user=None, auth=None):
    """
    Anonymizes ticket sales and personal attendee/billing data on an order
    without disabling or altering the associated user account.
    """
    with scope(organizer=order.event.organizer, event=order.event):
        if not is_order_event_ended(order):
            raise ValidationError(_('Order ticketing data cannot be anonymized before the associated event has ended.'))

        # 1. Anonymize Order contact fields
        order.email = f"anonymized-order-{order.code}@eventyay.local"
        order.phone = None
        order.email_known_to_work = False

        # Remove personal contact details from order meta_info
        d = order.meta_info_data
        if d:
            if 'contact_form_data' in d:
                del d['contact_form_data']
            order.meta_info = json.dumps(d)

        if order.comment:
            order.comment = "Anonymized order ticketing data"

        order.save(update_fields=['email', 'phone', 'email_known_to_work', 'meta_info', 'comment'])

        # 2. Anonymize OrderPosition / Attendee details
        for pos in order.all_positions.all():
            pos.attendee_email = f"anonymized-ticket-{pos.pk}@eventyay.local"
            pos.attendee_name_cached = None
            pos.attendee_name_parts = {}
            pos.company = None
            pos.street = None
            pos.zipcode = None
            pos.city = None
            pos.state = None
            pos.country = None

            pos_d = pos.meta_info_data
            if pos_d:
                if 'attendee_form_data' in pos_d:
                    del pos_d['attendee_form_data']
                pos.meta_info = json.dumps(pos_d)

            pos.save(update_fields=[
                'attendee_email', 'attendee_name_cached', 'attendee_name_parts',
                'company', 'street', 'zipcode', 'city', 'state', 'country', 'meta_info'
            ])

        # 3. Anonymize InvoiceAddress details if present
        try:
            ia = order.invoice_address
            if ia:
                ia.name_cached = ""
                ia.name_parts = {}
                ia.company = ""
                ia.street = ""
                ia.zipcode = ""
                ia.city = ""
                ia.state = ""
                ia.country = ""
                ia.vat_id = ""
                ia.custom_field = ""
                ia.internal_reference = ""
                ia.beneficiary = ""
                ia.save(update_fields=[
                    'name_cached', 'name_parts', 'company', 'street', 'zipcode',
                    'city', 'state', 'country', 'vat_id', 'custom_field', 'internal_reference', 'beneficiary'
                ])
        except InvoiceAddress.DoesNotExist:
            pass

        # 4. Shred Invoices and generated invoice PDFs
        for inv in order.invoices.filter(shredded=False):
            if inv.file:
                try:
                    inv.file.delete(save=False)
                except (OSError, IOError):
                    logger.exception('Failed to delete invoice file: %s', inv.file)
                inv.file = None
            inv.shredded = True
            inv.introductory_text = '█'
            inv.additional_text = '█'
            inv.invoice_to = '█'
            inv.payment_provider_text = '█'
            inv.save(update_fields=['file', 'shredded', 'introductory_text', 'additional_text', 'invoice_to', 'payment_provider_text'])
            inv.lines.update(description='█')

        # 5. Anonymize / clear QuestionAnswer records for position/order
        answers = QuestionAnswer.objects.filter(orderposition__order=order)
        for ans in answers:
            if ans.file:
                try:
                    ans.file.delete(save=False)
                except (OSError, IOError):
                    logger.exception('Failed to delete question answer file: %s', ans.file)
                ans.file = None
            ans.options.clear()
            ans.answer = "█"
            ans.save(update_fields=['answer', 'file'])

        # 6. Shred payment and refund information (e.g. bank transfer IBAN/payer details)
        provs = order.event.get_payment_providers()
        for payment in order.payments.all():
            pprov = provs.get(payment.provider)
            if pprov:
                try:
                    pprov.shred_payment_info(payment)
                except Exception:
                    logger.exception('Failed to shred payment info via provider %s, falling back to empty info', payment.provider)
                    payment.info = '{}'
                    payment.save(update_fields=['info'])
            elif payment.info:
                payment.info = '{}'
                payment.save(update_fields=['info'])
        for refund in order.refunds.all():
            pprov = provs.get(refund.provider)
            if pprov:
                try:
                    pprov.shred_payment_info(refund)
                except Exception:
                    logger.exception('Failed to shred refund info via provider %s, falling back to empty info', refund.provider)
                    refund.info = '{}'
                    refund.save(update_fields=['info'])
            elif refund.info:
                refund.info = '{}'
                refund.save(update_fields=['info'])

        # 7. Delete cached tickets for position and order
        CachedTicket.objects.filter(order_position__order=order).delete()
        CachedCombinedTicket.objects.filter(order=order).delete()

        # 8. Shred personal fields from past LogEntries for this order
        for le in order.all_logentries():
            shred_log_fields(le, banlist=[
                'old_email', 'new_email', 'recipient', 'message', 'subject',
                'old_phone', 'new_phone', 'attendee_name', 'attendee_name_parts',
                'company', 'street', 'zipcode', 'city', 'name_parts', 'name_cached'
            ])
            if le.action_type == 'eventyay.event.order.modified' and le.data:
                d = le.parsed_data
                changed = False
                if 'data' in d and isinstance(d['data'], list):
                    for i, row in enumerate(d['data']):
                        if isinstance(row, dict):
                            for k in row:
                                if k in ('attendee_name', 'attendee_email', 'company', 'street', 'zipcode', 'city', 'state', 'country'):
                                    d['data'][i][k] = '█'
                                elif k == 'attendee_name_parts':
                                    d['data'][i][k] = {'_legacy': '█'}
                                elif k not in ('product', 'variation', 'price', 'secret', 'addon_to'):
                                    d['data'][i][k] = '█'
                            changed = True
                if 'invoice_data' in d and isinstance(d['invoice_data'], dict):
                    for field in d['invoice_data']:
                        if d['invoice_data'][field]:
                            d['invoice_data'][field] = '█'
                    changed = True
                if changed:
                    le.data = json.dumps(d)
                    le.shredded = True
                    le.save(update_fields=['data', 'shredded'])

        # 9. Audit log action
        order.log_action('eventyay.event.order.anonymized', user=user, auth=auth)
