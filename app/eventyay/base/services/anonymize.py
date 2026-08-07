import json
import logging
from django.db import transaction
from eventyay.base.models import (
    CachedCombinedTicket,
    CachedTicket,
    InvoiceAddress,
    Order,
    QuestionAnswer,
)
from eventyay.base.shredder import shred_log_fields

logger = logging.getLogger(__name__)


@transaction.atomic
def anonymize_order(order: Order, user=None):
    """
    Anonymizes ticket sales and personal attendee/billing data on an order
    without disabling or altering the associated user account.
    """
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
        if hasattr(order, 'invoice_address') and order.invoice_address:
            ia = order.invoice_address
            ia.name_cached = ""
            ia.name_parts = {}
            ia.company = ""
            ia.street = ""
            ia.zipcode = ""
            ia.city = ""
            ia.state = ""
            ia.vat_id = ""
            ia.internal_reference = ""
            ia.beneficiary = ""
            ia.save(update_fields=[
                'name_cached', 'name_parts', 'company', 'street', 'zipcode',
                'city', 'state', 'vat_id', 'internal_reference', 'beneficiary'
            ])
    except InvoiceAddress.DoesNotExist:
        pass

    # 4. Anonymize / clear QuestionAnswer records for position/order
    answers = QuestionAnswer.objects.filter(orderposition__order=order)
    for ans in answers:
        if ans.file:
            try:
                ans.file.delete(save=False)
            except Exception:
                logger.warning('Failed to delete question answer file: %s', ans.file, exc_info=True)
            ans.file = None
        ans.answer = "█"
        ans.save(update_fields=['answer', 'file'])

    # 5. Delete cached tickets for position and order
    CachedTicket.objects.filter(order_position__order=order).delete()
    CachedCombinedTicket.objects.filter(order=order).delete()

    # 6. Shred personal fields from past LogEntries for this order
    for le in order.all_logentries():
        shred_log_fields(le, banlist=[
            'old_email', 'new_email', 'recipient', 'message', 'subject',
            'old_phone', 'new_phone', 'attendee_name', 'attendee_name_parts',
            'company', 'street', 'zipcode', 'city', 'name_parts', 'name_cached'
        ])

    # 7. Audit log action
    order.log_action('eventyay.event.order.anonymized', user=user)
