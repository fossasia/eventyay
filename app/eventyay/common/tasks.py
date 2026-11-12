import logging
from pathlib import Path

from celery.exceptions import MaxRetriesExceededError
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Submission, User
from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, log_event
from eventyay.base.signals import periodic_task as base_periodic_task
from eventyay.celery_app import app
from eventyay.common.image import process_image
from eventyay.common.signals import periodic_task as common_periodic_task


logger = logging.getLogger(__name__)


@app.task(name='pretalx.process_image')
def task_process_image(*, model: str, pk: int, field: str, generate_thumbnail: bool):
    models = {
        'Event': Event,
        'Submission': Submission,
        'User': User,
    }
    if model not in models:
        return

    with scopes_disabled():
        instance = models[model].objects.filter(pk=pk).first()
        if not instance:
            return

        image = getattr(instance, field, None)
        if not image:
            return

        if not process_image(image=image, generate_thumbnail=generate_thumbnail):
            logger.error('Could not process image %s', image.name)


@app.task(name='pretalx.cleanup_file')
def task_cleanup_file(*, model: str, pk: int, field: str, path: str):
    models = {
        'Event': Event,
        'Submission': Submission,
        'User': User,
    }
    if model not in models:
        return

    with scopes_disabled():
        instance = models[model].objects.filter(pk=pk).first()
        if not instance:
            return

        file = getattr(instance, field, None)
        if file and file.path == path:
            # The save action that triggered this task did not go through and the file
            # is still in use, so we should not delete it.
            return

        real_path = Path(path)
        if real_path.exists():
            try:
                default_storage.delete(path)
            except OSError:  # pragma: no cover
                logger.error('Deleting file %s failed.', path)


@app.task(
    bind=True, name='eventyay.common.send_scheduled_queuedmail', max_retries=3, default_retry_delay=60, acks_late=True
)
def send_scheduled_queuedmail(self, mail_pk: int):
    """
    Celery task to send a specific QueuedMail at its scheduled time.

    Dispatched with eta=scheduled_at from orga compose views, bypassing the
    minimum_interval throttle on the periodic poller. Uses select_for_update to
    claim the row exclusively and prevent double-send with the poller fallback.
    """

    from eventyay.base.models.mail import QueuedMail
    from eventyay.common.exceptions import SendMailException

    try:
        with scopes_disabled(), transaction.atomic():
            mail = (
                QueuedMail.objects
                .select_for_update(skip_locked=True)
                .filter(pk=mail_pk, sent__isnull=True, is_draft=False)
                .first()
            )

            if mail is None:
                logger.debug(
                    "[ScheduledMail] QueuedMail ID %s: not found, already sent, or locked. Skipping.",
                    mail_pk,
                )
                return

            current_time = now()
            if mail.scheduled_at and mail.scheduled_at > current_time:
                countdown = max(1, int((mail.scheduled_at - current_time).total_seconds()))
                logger.info(
                    "[ScheduledMail] QueuedMail ID %s: scheduled for %s, rescheduling in %s seconds.",
                    mail_pk, mail.scheduled_at, countdown,
                )
                self.retry(countdown=countdown, args=[mail_pk], throw=False)
                return

            mail.send()
            logger.info("[ScheduledMail] QueuedMail ID %s sent successfully.", mail_pk)

    except SendMailException:
        logger.exception("[ScheduledMail] Failed to send QueuedMail ID %s", mail_pk)
    except Exception as exc:
        logger.exception("[ScheduledMail] Unexpected error for QueuedMail ID %s", mail_pk)
        try:
            self.retry(exc=exc, args=[mail_pk])
        except MaxRetriesExceededError:
            log_event('mail', 'mail.send', OUTCOME_FAILURE, error_code='retries_exhausted')
            logger.error('[ScheduledMail] Max retries exceeded for QueuedMail ID %s', mail_pk)


@app.task(
    bind=True, name='eventyay.common.send_draft_reminder_batch', max_retries=3, default_retry_delay=60, acks_late=True
)
def send_draft_reminder_batch(self, batch_id: int):
    from eventyay.base.models.draft_reminder import (
        DraftReminderBatch,
        DraftReminderBatchStatus,
        DraftReminderRecipient,
        DraftReminderRecipientStatus,
    )
    from eventyay.base.models.submission import SubmissionStates

    try:
        with scopes_disabled(), transaction.atomic():
            batch = (
                DraftReminderBatch.objects
                .select_for_update(skip_locked=True)
                .filter(pk=batch_id, status__in=[
                    DraftReminderBatchStatus.PENDING,
                    DraftReminderBatchStatus.SENDING,
                ])
                .first()
            )
            if batch is None:
                return

            batch.status = DraftReminderBatchStatus.SENDING
            batch.save(update_fields=['status'])

        with scopes_disabled():
            event = batch.event
            template = batch.template
            if not template:
                logger.error('[DraftReminder] Batch %s has no template, aborting.', batch_id)
                DraftReminderBatch.objects.filter(pk=batch_id).update(
                    status=DraftReminderBatchStatus.FAILED, completed_at=now(),
                )
                return

            pending = (
                DraftReminderRecipient.objects
                .filter(batch=batch, status=DraftReminderRecipientStatus.PENDING)
                .select_related('submission', 'user')
            )

            for recipient in pending.iterator():
                if recipient.submission.state != SubmissionStates.DRAFT:
                    recipient.status = DraftReminderRecipientStatus.SENT
                    recipient.sent_at = now()
                    recipient.save(update_fields=['status', 'sent_at'])
                    continue
                try:
                    template.to_mail(
                        user=recipient.user,
                        event=event,
                        locale=recipient.submission.get_email_locale(recipient.user.locale),
                        context_kwargs={
                            'submission': recipient.submission,
                            'user': recipient.user,
                        },
                        skip_queue=True,
                        commit=False,
                    )
                    recipient.status = DraftReminderRecipientStatus.SENT
                    recipient.sent_at = now()
                    recipient.save(update_fields=['status', 'sent_at'])
                except Exception as exc:
                    error_type = type(exc).__name__
                    recipient.status = DraftReminderRecipientStatus.FAILED
                    recipient.error = error_type[:500]
                    recipient.save(update_fields=['status', 'error'])
                    logger.warning(
                        '[DraftReminder] Failed to send to user %s for submission %s: %s',
                        recipient.user_id, recipient.submission_id, error_type,
                    )

            with transaction.atomic():
                batch = (
                    DraftReminderBatch.objects
                    .select_for_update()
                    .get(pk=batch_id)
                )
                counts = (
                    DraftReminderRecipient.objects
                    .filter(batch=batch)
                    .aggregate(
                        sent=models.Count('pk', filter=models.Q(status=DraftReminderRecipientStatus.SENT)),
                        failed=models.Count('pk', filter=models.Q(status=DraftReminderRecipientStatus.FAILED)),
                        pending=models.Count('pk', filter=models.Q(status=DraftReminderRecipientStatus.PENDING)),
                    )
                )
                batch.sent_count = counts['sent']
                batch.failed_count = counts['failed']

                if counts['pending'] == 0:
                    batch.status = DraftReminderBatchStatus.COMPLETED
                    batch.completed_at = now()
                else:
                    batch.status = DraftReminderBatchStatus.FAILED

                batch.save(update_fields=['sent_count', 'failed_count', 'status', 'completed_at'])

            log_event(
                'mail', 'mail.draft_reminder_batch', OUTCOME_SUCCESS,
                event_id=event.pk, object_id=batch_id,
                recipient_count=counts['sent'],
            )

    except Exception as exc:
        logger.exception('[DraftReminder] Unexpected error for batch %s', batch_id)
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            with scopes_disabled():
                DraftReminderBatch.objects.filter(pk=batch_id).update(
                    status=DraftReminderBatchStatus.FAILED,
                    completed_at=now(),
                )
            log_event('mail', 'mail.draft_reminder_batch', OUTCOME_FAILURE, error_code='retries_exhausted')


@app.task(name='eventyay.common.tasks.send_periodic_signal')
def send_periodic_signal():
    """
    Celery task that sends the periodic_task signals.

    This task is intended to be run periodically by Celery beat (for example,
    via django-celery-beat's DatabaseScheduler) and triggers all signal receivers
    listening to the periodic_task signals, including process_scheduled_emails.

    Both the ``eventyay.common.signals`` and the ``eventyay.base.signals``
    ``periodic_task`` signals are sent, since receivers are registered on both
    (the latter holds e.g. the ECB rate fetch and the billing jobs). Receiver
    errors are logged and do not stop the remaining receivers.

    Celery beat loads this task from CELERY_BEAT_SCHEDULE with a one-minute
    interval.
    """
    logger.debug('Sending periodic_task signals')
    for signal in (common_periodic_task, base_periodic_task):
        for receiver, response in signal.send_robust(sender=None):
            if isinstance(response, Exception):
                log_event('core', 'periodic_task.receiver', OUTCOME_FAILURE, error_code='receiver_error')
                logger.error(
                    'Periodic task receiver %s.%s failed',
                    receiver.__module__,
                    receiver.__name__,
                    exc_info=response,
                )
    logger.debug('Periodic_task signals sent successfully')
