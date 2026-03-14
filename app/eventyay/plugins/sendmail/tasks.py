import logging

from eventyay.base.models import Event
from eventyay.base.services.tasks import ProfiledEventTask
from eventyay.celery_app import app


logger = logging.getLogger(__name__)


@app.task(base=ProfiledEventTask, bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def send_queued_mail(self, event_id: int, queued_mail_id: int):
    from eventyay.plugins.sendmail.models import EmailQueue
    from celery.exceptions import MaxRetriesExceededError

    if isinstance(event_id, Event):
        original_event_id = event_id.pk
        event = event_id
    else:
        original_event_id = event_id
        event = Event.objects.get(id=original_event_id)

    try:
        qm = EmailQueue.objects.get(pk=queued_mail_id, event=event)
        # Execute the actual mail transport in this task so outbox state reflects real send attempts.
        result = qm.send(async_send=False)

        if not result:
            logger.warning("[SendMail] EmailQueue ID %s: no recipients to send to.", queued_mail_id)
        elif not qm.sent_at:
            logger.warning("[SendMail] EmailQueue ID %s: partially sent, some recipients failed.", queued_mail_id)
        else:
            logger.info("[SendMail] EmailQueue ID %s: all emails sent successfully.", queued_mail_id)

    except Event.DoesNotExist:
        logger.error("[SendMail] Event ID %s not found.", original_event_id)

    except EmailQueue.DoesNotExist:
        logger.error("[SendMail] EmailQueue ID %s not found for event ID %s.", queued_mail_id, original_event_id)

    except Exception as exc:
        logger.exception("[SendMail] Unexpected error for EmailQueue ID %s", queued_mail_id)
        try:
            self.retry(exc=exc, args=[original_event_id, queued_mail_id])
        except MaxRetriesExceededError:
            logger.error("[SendMail] Max retries exceeded for EmailQueue ID %s", queued_mail_id)


@app.task(bind=True)
def send_scheduled_mail(self, rule_id: int):
    from eventyay.plugins.sendmail.models import ScheduledMail, EmailQueue, EmailQueueFilter, ComposingFor, ScheduledMailLog
    from django.utils.timezone import now
    from django.db.models import Exists, OuterRef, Q
    from eventyay.base.models import Order, OrderPosition

    try:
        rule = ScheduledMail.objects.get(pk=rule_id)
    except ScheduledMail.DoesNotExist:
        return

    # Update execution time to prevent double-firing
    rule.last_execution = now()
    rule.save(update_fields=['last_execution'])
    
    event = rule.event
    
    qs = Order.objects.filter(event=event)
    statusq = Q(status__in=rule.order_status)
    if 'overdue' in rule.order_status:
        statusq |= Q(status=Order.STATUS_PENDING, expires__lt=now())
    if 'pa' in rule.order_status:
        statusq |= Q(status=Order.STATUS_PENDING, require_approval=True)
    if 'na' in rule.order_status:
        statusq |= Q(status=Order.STATUS_PENDING, require_approval=False)
    orders = qs.filter(statusq)

    opq = OrderPosition.objects.filter(
        order=OuterRef('pk'),
        canceled=False,
        product_id__in=rule.products,
    )

    if rule.has_filter_checkins:
        ql = []
        if rule.not_checked_in:
            ql.append(Q(checkins__list_id=None))
        if rule.checkin_lists:
            ql.append(Q(checkins__list_id__in=rule.checkin_lists))
        if len(ql) == 2:
            opq = opq.filter(ql[0] | ql[1])
        elif ql:
            opq = opq.filter(ql[0])
        else:
            opq = opq.none()

    if rule.subevent:
        opq = opq.filter(subevent_id=rule.subevent)

    orders = orders.annotate(match_pos=Exists(opq)).filter(match_pos=True).distinct()

    if not orders.exists():
        ScheduledMailLog.objects.create(rule=rule, recipient_count=0, error="No orders matched filters.")
        return

    try:
        qm = EmailQueue.objects.create(
            event=event,
            user=None,
            subject=rule.subject.data if getattr(rule.subject, 'data', None) else rule.subject,
            message=rule.message.data if getattr(rule.message, 'data', None) else rule.message,
            attachments=[],
            locale=event.settings.locale,
            reply_to=event.settings.get('contact_mail') or '',
            bcc=event.settings.get('mail_bcc'),
            composing_for=ComposingFor.ATTENDEES,
        )

        EmailQueueFilter.objects.create(
            mail=qm,
            recipients=rule.recipients,
            order_status=rule.order_status,
            orders=list(orders.values_list('pk', flat=True)),
            products=rule.products,
            checkin_lists=rule.checkin_lists,
            has_filter_checkins=rule.has_filter_checkins,
            not_checked_in=rule.not_checked_in,
            subevent=rule.subevent,
            subevents_from=None,
            subevents_to=None,
            order_created_from=None,
            order_created_to=None,
        )

        qm.populate_to_users()
        
        recipient_count = qm.recipients.count()
        ScheduledMailLog.objects.create(rule=rule, recipient_count=recipient_count)
        
        if recipient_count > 0:
            send_queued_mail.apply_async(args=[event.pk, qm.pk])

    except Exception as e:
        logger.exception("[SendMail] Failed to generate ScheduledMail %s", rule_id)
        ScheduledMailLog.objects.create(rule=rule, recipient_count=0, error=str(e))


@app.task(name='eventyay.plugins.sendmail.tasks.process_scheduled_mails')
def process_scheduled_mails():
    from eventyay.plugins.sendmail.models import ScheduledMail
    
    rules = ScheduledMail.objects.filter(enabled=True)
    for rule in rules:
        try:
            if rule.is_due():
                send_scheduled_mail.apply_async(args=[rule.pk])
        except Exception:
            logger.exception("Failed to process ScheduledMail rule %s", rule.pk)
