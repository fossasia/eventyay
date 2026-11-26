from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.models import Order


ANONYMIZED_ORDER_EDIT_ERROR = _('Personal data cannot be edited on an anonymized order.')


def lock_order_for_identity_edit(order: Order) -> Order:
    with scope(event=order.event_id):
        return Order.objects.select_for_update().get(event_id=order.event_id, pk=order.pk)


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
def anonymize_order(order: Order, user=None, auth=None) -> None:
    """
    Replaces the identity of the buyer and attendees of an order once its event has ended.

    Nothing is deleted: positions, question answers, payments, invoices and check-ins stay and remain
    linked to an anonymous buyer. The user account that placed the order is not changed, but it no
    longer sees the order because accounts are linked to orders by email address only.
    """
    with scope(organizer=order.event.organizer, event=order.event):
        if not is_order_event_ended(order):
            raise ValidationError(_('Order ticketing data cannot be anonymized before the associated event has ended.'))

        order.refresh_from_db(from_queryset=Order.objects.select_for_update())
        for anonymizer in order.event.get_ticketing_anonymizers().values():
            anonymizer.anonymize_order(order)

        order.is_anonymized = True
        order.save(update_fields=['is_anonymized'])
        order.log_action('eventyay.event.order.anonymized', user=user, auth=auth)
