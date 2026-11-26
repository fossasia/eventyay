from datetime import timedelta

from django.db.models import Q
from django.dispatch import receiver
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, User, WaitingListEntry
from eventyay.base.models.waitinglist import WaitingListBusy, WaitingListException
from eventyay.base.services.tasks import EventTask
from eventyay.base.signals import order_canceled, order_changed, periodic_task
from eventyay.celery_app import app


@app.task(base=EventTask, bind=True)
def assign_automatically(self, event: Event, user_id: int = None, subevent_id: int = None, *, sent=0):
    """Assign eligible entries, retrying temporary conflicts with serializable identifiers."""
    if user_id:
        user = User.objects.get(id=user_id)
    else:
        user = None

    qs = (
        WaitingListEntry.objects.filter(event=event, voucher__isnull=True)
        .select_related('product', 'variation', 'subevent')
        .order_by('-priority', 'created')
    )

    if subevent_id and event.has_subevents:
        subevent = event.subevents.get(id=subevent_id)
        qs = qs.filter(subevent=subevent)
        subevent_id = subevent.pk

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
        try:
            wle.send_voucher(user=user, eligible=eligible)
        except WaitingListBusy as exc:
            raise self.retry(
                args=(event.pk, user_id, subevent_id), kwargs={'sent': sent}, exc=exc, countdown=5, max_retries=5,
            )
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
    """Trigger waiting-list assignment after an order cancellation."""
    assign_for_order(sender, order)


@receiver(signal=order_changed, dispatch_uid='waitinglist_order_changed')
def on_order_changed(sender, order, **kwargs):
    """Trigger waiting-list assignment after an order change."""
    assign_for_order(sender, order)


def assign_for_order(event, order):
    """Queue assignment once per affected date when automatic assignment is enabled."""
    if (
        not event.settings.get('waiting_list_enabled', as_type=bool)
        or not event.settings.get('waiting_list_auto', as_type=bool)
        or not (event.presale_is_running or event.has_subevents)
    ):
        return

    subevent_ids = []
    if event.has_subevents:
        with scope(event=event, organizer=event.organizer):
            subevent_ids = list(
                order.positions.exclude(subevent_id__isnull=True)
                .order_by().values_list('subevent_id', flat=True).distinct()
            )
    if not subevent_ids:
        assign_automatically.apply_async(args=(event.pk,))
        return
    for subevent_id in subevent_ids:
        assign_automatically.apply_async(args=(event.pk, None, subevent_id))
