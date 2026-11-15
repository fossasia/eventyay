from datetime import timedelta

from django.db.models import Q
from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, User, WaitingListEntry
from eventyay.base.models.waitinglist import WaitingListException, WaitingListUnavailable
from eventyay.base.services.tasks import EventTask
from eventyay.base.signals import order_canceled, order_changed, periodic_task
from eventyay.celery_app import app


@app.task(base=EventTask)
def assign_automatically(event: Event, user_id: int = None, subevent_id: int = None):
    if user_id:
        user = User.objects.get(id=user_id)
    else:
        user = None

    gone = set()

    qs = (
        WaitingListEntry.objects.filter(event=event, voucher__isnull=True)
        .select_related('product', 'variation', 'subevent')
        .order_by('-priority', 'created')
    )

    if subevent_id and event.has_subevents:
        subevent = event.subevents.get(id=subevent_id)
        qs = qs.filter(subevent=subevent)

    sent = 0

    def eligible(entry):
        """Check automatic assignment rules against the current, locked entry."""
        date = entry.subevent
        return (
            (not subevent_id or not event.has_subevents or entry.subevent_id == subevent_id)
            and (not date or date.active)
            and (date or entry.event).presale_is_running
            and entry.product.is_available()
        )

    for wle in qs:
        if (wle.product, wle.variation, wle.subevent) in gone:
            continue

        try:
            wle.send_voucher(user=user, eligible=eligible)
        except WaitingListUnavailable:
            gone.add((wle.product, wle.variation, wle.subevent))
        except WaitingListException:
            continue
        else:
            sent += 1

    return sent


@receiver(signal=periodic_task)
@scopes_disabled()
def process_waitinglist(sender, **kwargs):
    qs = (
        Event.objects.filter(live=True)
        .exclude(
            Q(date_to__isnull=True) | Q(date_to__lt=now() - timedelta(days=14)),
            Q(presale_end__isnull=True) | Q(presale_end__lt=now() - timedelta(days=14)),
            has_subevents=False,
            date_from__lt=now() - timedelta(days=14),
        )
        .prefetch_related('_settings_objects', 'organizer___settings_objects')
        .select_related('organizer')
    )
    for e in qs:
        if e.settings.waiting_list_auto and (e.presale_is_running or e.has_subevents):
            assign_automatically.apply_async(args=(e.pk,))


@receiver(signal=order_canceled, dispatch_uid='waitinglist_order_canceled')
def on_order_canceled(sender, order, **kwargs):
    """
    When an order is canceled, immediately trigger waiting list assignment
    if automatic assignment is enabled for the event.
    """
    event = sender
    
    # Check if waiting list auto-assignment is enabled
    if not event.settings.get('waiting_list_enabled', as_type=bool):
        return
    
    if not event.settings.get('waiting_list_auto', as_type=bool):
        return
    
    # Check if event is still selling tickets
    if not (event.presale_is_running or event.has_subevents):
        return
    
    # Get unique subevents from canceled order positions
    subevents = set()
    for position in order.positions.all():
        if position.subevent:
            subevents.add(position.subevent.pk)
    
    # Trigger assignment for the main event
    if not subevents or not event.has_subevents:
        assign_automatically.apply_async(args=(event.pk,))
    else:
        # Trigger assignment for each affected subevent
        for subevent_id in subevents:
            assign_automatically.apply_async(args=(event.pk, None, subevent_id))


@receiver(signal=order_changed, dispatch_uid='waitinglist_order_changed')
def on_order_changed(sender, order, **kwargs):
    """
    When an order is modified (e.g., positions canceled), immediately trigger
    waiting list assignment if automatic assignment is enabled for the event.
    """
    event = sender
    
    # Check if waiting list auto-assignment is enabled
    if not event.settings.get('waiting_list_enabled', as_type=bool):
        return
    
    if not event.settings.get('waiting_list_auto', as_type=bool):
        return
    
    # Check if event is still selling tickets
    if not (event.presale_is_running or event.has_subevents):
        return
    
    # Get unique subevents from order positions
    subevents = set()
    for position in order.positions.all():
        if position.subevent:
            subevents.add(position.subevent.pk)
    
    # Trigger assignment for the main event
    if not subevents or not event.has_subevents:
        assign_automatically.apply_async(args=(event.pk,))
    else:
        # Trigger assignment for each affected subevent
        for subevent_id in subevents:
            assign_automatically.apply_async(args=(event.pk, None, subevent_id))
