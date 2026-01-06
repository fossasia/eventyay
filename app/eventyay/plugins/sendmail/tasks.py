import logging

from django.utils.timezone import now

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

        if qm.scheduled_at and qm.scheduled_at > now():
            logger.info("[SendMail] EmailQueue ID %s: scheduled for %s, skipping.", queued_mail_id, qm.scheduled_at)
            return

        result = qm.send(async_send=True)

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
