import json
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.db.models.functions import Coalesce
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.anonymizer import BaseTicketingAnonymizer
from eventyay.base.models import CartPosition, Event, EventAnonymizationRun, Invoice, Order, User, WaitingListEntry
from eventyay.base.services.tasks import EventTask
from eventyay.base.settings import GlobalSettingsObject
from eventyay.base.shredder import shred_log_fields
from eventyay.celery_app import app
from eventyay.core.permissions import ORGANIZER_ROLES
from eventyay.helpers.anonymization import ANONYMIZED_NAME, anonymized_email
from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueToUser


def anonymization_available_from(event: Event):
    """When ticketing data of ``event`` may be anonymized, or None if the event has no end date."""
    end = event.date_to or event.date_from
    if event.has_subevents:
        last = event.subevents.aggregate(last=Max(Coalesce('date_to', 'date_from')))['last']
        if last:
            end = max(end, last) if end else last
    if end is None:
        return None
    days = GlobalSettingsObject().settings.get('ticketing_retention_manual_min_days', default='14', as_type=int)
    return end + timedelta(days=days)


def check_event_end(event: Event) -> None:
    available_from = anonymization_available_from(event)
    if available_from is None or now() < available_from:
        raise ValidationError(_('The waiting period after this event has not ended.'))


def clean_cart_meta_info(raw_meta: str | None) -> str | None:
    if not raw_meta:
        return raw_meta
    try:
        meta = json.loads(raw_meta)
    except ValueError:
        return '{}'
    if not isinstance(meta, dict):
        return '{}'
    meta.pop('attendee_form_data', None)
    return json.dumps(meta)


def anonymize_event_records(event: Event) -> dict[str, int]:
    organizers = User.objects.filter(event_grants__event=event, event_grants__role__in=ORGANIZER_ROLES)
    users = (
        User.objects.filter(event=event, is_staff=False)
        .exclude(token_id__endswith=':orga')
        .exclude(teams__isnull=False)
        .exclude(pk__in=organizers)
    )
    video_count = users.update(profile={}, token_id=None, client_id=None, fullname=None, email=None)
    waiting = WaitingListEntry.objects.filter(event=event).select_related('voucher')
    waiting_count = 0
    for entry in waiting.iterator():
        original_email = entry.email
        WaitingListEntry.objects.filter(pk=entry.pk).update(
            name_parts={'_legacy': ANONYMIZED_NAME},
            name_cached=ANONYMIZED_NAME,
            email=anonymized_email('waiting'),
            phone=None,
        )
        if entry.voucher_id and entry.voucher.comment:
            comment = entry.voucher.comment
            if original_email and original_email in comment:
                entry.voucher.comment = comment.replace(original_email, ANONYMIZED_NAME)
                entry.voucher.save(update_fields=['comment'])
            elif '@' in comment:
                entry.voucher.comment = '█'
                entry.voucher.save(update_fields=['comment'])
        waiting_count += 1
    for log_entry in event.logentry_set.filter(action_type='eventyay.voucher.added.waitinglist').exclude(data=''):
        shred_log_fields(log_entry, banlist=['email', 'name', 'name_parts', 'phone'])
    carts = CartPosition.objects.filter(event=event, expires__lte=now())
    cart_count = 0
    for cart in carts.iterator():
        carts.filter(pk=cart.pk).update(
            attendee_name_parts={},
            attendee_name_cached=None,
            attendee_email=None,
            city=None,
            company=None,
            job_title=None,
            street=None,
            zipcode=None,
            state=None,
            country=None,
            cart_id=None,
            meta_info=clean_cart_meta_info(cart.meta_info),
        )
        cart_count += 1
    messages = EmailQueue.objects.filter(event=event, composing_for=ComposingFor.ATTENDEES)
    messages.exclude(bcc__isnull=True).exclude(bcc='').update(bcc='')
    recipients = EmailQueueToUser.objects.filter(mail__in=messages, team__isnull=True)
    mail_count = 0
    for pk in recipients.values_list('pk', flat=True).iterator():
        recipients.filter(pk=pk).update(email=anonymized_email('recipient'), error=None)
        mail_count += 1
    return {'video_users': video_count, 'waiting_list': waiting_count, 'carts': cart_count, 'recipients': mail_count}


def flush_pending_file_deletions(run: EventAnonymizationRun) -> None:
    if not run.pending_file_deletions:
        return
    storage = Invoice._meta.get_field('file').storage
    for path in tuple(run.pending_file_deletions):
        storage.delete(path)
        with transaction.atomic():
            locked_run = EventAnonymizationRun.objects.select_for_update().get(pk=run.pk)
            locked_run.pending_file_deletions = [
                pending for pending in locked_run.pending_file_deletions if pending != path
            ]
            locked_run.save(update_fields=['pending_file_deletions'])
            run.pending_file_deletions = locked_run.pending_file_deletions


def process_order_ids(
    event: Event,
    run: EventAnonymizationRun,
    anonymizers: dict[str, BaseTicketingAnonymizer],
    order_ids: list[int],
) -> tuple[EventAnonymizationRun, bool]:
    for pk in order_ids:
        with transaction.atomic():
            run = EventAnonymizationRun.objects.select_for_update().get(pk=run.pk)
            if run.status == run.Status.COMPLETED:
                return run, True
            order = Order.objects.select_for_update().filter(event=event, pk=pk).first()
            if order and not order.is_anonymized:
                pending_deletions: list[str] = []
                for identifier, handler in anonymizers.items():
                    handler.pending_file_deletions = pending_deletions
                    handler.anonymize_order(order)
                    run.counts[identifier] = run.counts.get(identifier, 0) + 1
                order.is_anonymized = True
                order.save(update_fields=['is_anonymized'])
                if pending_deletions:
                    run.pending_file_deletions = [*run.pending_file_deletions, *pending_deletions]
            if pk > run.last_order_id:
                run.last_order_id = pk
            run.status = run.Status.RUNNING
            run.error = ''
            run.finished = None
            run.save()
        flush_pending_file_deletions(run)
    return run, False


class AnonymizationTask(EventTask):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        event_id = kwargs.get('event_id') or kwargs.get('event') or args[0]
        with scope(event=event_id):
            EventAnonymizationRun.objects.filter(event_id=event_id, status=EventAnonymizationRun.Status.RUNNING).update(
                status=EventAnonymizationRun.Status.FAILED, error=type(exc).__name__, finished=now()
            )
        super().on_failure(exc, task_id, args, kwargs, einfo)


@app.task(base=AnonymizationTask, queue='longrunning', acks_late=True, reject_on_worker_lost=True)
def anonymize_event(event: Event, trigger: str, user: int | None = None) -> int:
    trigger = EventAnonymizationRun.Trigger(trigger)
    with scope(event=event, organizer=event.organizer):
        check_event_end(event)
        run, _created = EventAnonymizationRun.objects.get_or_create(
            event=event, defaults={'trigger': trigger, 'requested_by_id': user}
        )
        anonymizers = event.get_ticketing_anonymizers()
        flush_pending_file_deletions(run)
        while True:
            ids = list(
                Order.objects.filter(event=event, pk__gt=run.last_order_id)
                .order_by('pk')
                .values_list('pk', flat=True)[:100]
            )
            if not ids:
                ids = list(
                    Order.objects.filter(event=event, pk__lte=run.last_order_id, is_anonymized=False)
                    .order_by('pk')
                    .values_list('pk', flat=True)[:100]
                )
            if ids:
                run, completed = process_order_ids(event, run, anonymizers, ids)
                if completed:
                    return run.pk
                continue
            flush_pending_file_deletions(run)
            # Orders are created and imported under the event lock, so taking it here means the check below
            # cannot pass while an order is still being committed.
            with event.lock(blocking=True, blocking_timeout=30), transaction.atomic():
                run = EventAnonymizationRun.objects.select_for_update().get(pk=run.pk)
                if run.status == run.Status.COMPLETED:
                    return run.pk
                if Order.objects.filter(event=event, is_anonymized=False).exists() or run.pending_file_deletions:
                    continue
                run.counts.update(anonymize_event_records(event))
                run.status = run.Status.COMPLETED
                run.finished = now()
                run.error = ''
                run.save()
                event.log_action('eventyay.event.ticketing_data.anonymized', data=run.counts, user=run.requested_by)
                return run.pk
