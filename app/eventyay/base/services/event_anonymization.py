from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.db.models.functions import Coalesce
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_scopes import scope

from eventyay.base.models import CartPosition, Event, EventAnonymizationRun, Order, User, WaitingListEntry
from eventyay.base.services.tasks import EventTask
from eventyay.base.settings import GlobalSettingsObject
from eventyay.celery_app import app
from eventyay.core.permissions import ORGANIZER_ROLES
from eventyay.helpers.anonymization import ANONYMIZED_NAME, anonymized_email
from eventyay.plugins.sendmail.models import ComposingFor, EmailQueue, EmailQueueToUser


def check_event_end(event: Event) -> None:
    end = event.date_to or event.date_from
    if event.has_subevents:
        last = event.subevents.aggregate(last=Max(Coalesce('date_to', 'date_from')))['last']
        if last:
            end = max(end, last) if end else last
    days = GlobalSettingsObject().settings.get('ticketing_retention_manual_min_days', default='14', as_type=int)
    if end is None or now() < end + timedelta(days=days):
        raise ValidationError(_('The waiting period after this event has not ended.'))


def anonymize_event_records(event: Event) -> dict[str, int]:
    organizers = User.objects.filter(event_grants__event=event, event_grants__role__in=ORGANIZER_ROLES)
    users = (
        User.objects.filter(event=event, is_staff=False)
        .exclude(token_id__endswith=':orga')
        .exclude(teams__isnull=False)
        .exclude(pk__in=organizers)
    )
    video_count = users.update(profile={}, token_id=None, client_id=None)
    waiting = WaitingListEntry.objects.filter(event=event)
    waiting_count = 0
    for pk in waiting.values_list('pk', flat=True).iterator():
        waiting.filter(pk=pk).update(
            name_parts={'_legacy': ANONYMIZED_NAME},
            name_cached=ANONYMIZED_NAME,
            email=anonymized_email('waiting'),
            phone=None,
        )
        waiting_count += 1
    carts = CartPosition.objects.filter(event=event, expires__lte=now())
    cart_count = 0
    for cart in carts.iterator():
        meta = cart.meta_info_data
        meta.pop('attendee_form_data', None)
        cart.meta_info_data = meta
        carts.filter(pk=cart.pk).update(
            attendee_name_parts={},
            attendee_name_cached=None,
            attendee_email=None,
            city=None,
            company=None,
            street=None,
            zipcode=None,
            state=None,
            country=None,
            cart_id=None,
            meta_info=cart.meta_info,
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
        while True:
            ids = list(
                Order.objects.filter(event=event, pk__gt=run.last_order_id)
                .order_by('pk')
                .values_list('pk', flat=True)[:100]
            )
            for pk in ids:
                with transaction.atomic():
                    run = EventAnonymizationRun.objects.select_for_update().get(pk=run.pk)
                    if run.status == run.Status.COMPLETED:
                        return run.pk
                    if pk <= run.last_order_id:
                        continue
                    order = Order.objects.select_for_update().filter(event=event, pk=pk).first()
                    if order:
                        for identifier, handler in anonymizers.items():
                            handler.anonymize_order(order)
                            run.counts[identifier] = run.counts.get(identifier, 0) + 1
                    run.last_order_id = pk
                    run.status = run.Status.RUNNING
                    run.error = ''
                    run.finished = None
                    run.save()
            if not ids:
                break
        with transaction.atomic():
            run = EventAnonymizationRun.objects.select_for_update().get(pk=run.pk)
            if run.status != run.Status.COMPLETED:
                run.counts.update(anonymize_event_records(event))
                run.status = run.Status.COMPLETED
                run.finished = now()
                run.error = ''
                run.save()
                event.log_action('eventyay.event.ticketing_data.anonymized', data=run.counts, user=run.requested_by)
        return run.pk
