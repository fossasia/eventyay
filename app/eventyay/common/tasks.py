import logging
from pathlib import Path
from smtplib import SMTPException

from celery.exceptions import MaxRetriesExceededError
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.entitlements import record_usage
from eventyay.base.models import Event, Organizer, Submission, SubmissionStates, User
from eventyay.base.models.draft_reminder import (
    DraftReminderBatch,
    DraftReminderBatchStatus,
    DraftReminderRecipient,
    DraftReminderRecipientStatus,
)
from eventyay.base.models.mail import MailTemplate
from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, log_event
from eventyay.base.signals import periodic_task as base_periodic_task
from eventyay.celery_app import app
from eventyay.common.image import process_image
from eventyay.common.mail import RETRY_ERRNOS, RETRY_SMTP_CODES, SendMailException
from eventyay.common.signals import periodic_task as common_periodic_task


logger = logging.getLogger(__name__)


class DraftReminderTransportError(SendMailException):
    """Raised for transient mail transport errors during draft reminder dispatch to trigger Celery retry."""

    pass


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


def reconcile_draft_reminder_batch_allowance(batch: DraftReminderBatch) -> None:
    """Reconciles unused allowance for a completed or failed draft reminder batch."""
    if batch.reconciled:
        return
    unsent_count = batch.total_count - batch.sent_count
    if unsent_count > 0:
        event = batch.event
        accounting_period = (
            batch.created_at.strftime('%Y-%m')
            if batch.created_at
            else now().strftime('%Y-%m')
        )
        with transaction.atomic():
            Organizer.objects.select_for_update().get(pk=event.organizer_id)
            source_id = batch.uuid.hex
            record_usage(
                event.organizer,
                'email.bulk.monthly',
                quantity=-unsent_count,
                unit='emails',
                source_type='bulk_email',
                source_id=source_id,
                idempotency_key=f'bulk_mail_draft_reminders_{source_id}_release',
                event=event,
                accounting_period=accounting_period,
                metadata={
                    'batch_uuid': source_id,
                    'batch_created_at': batch.created_at.isoformat() if batch.created_at else None,
                    'accounting_period': accounting_period,
                },
            )
    batch.reconciled = True
    batch.save(update_fields=['reconciled'])


@app.task(
    bind=True,
    name='eventyay.common.send_draft_reminder_batch',
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def send_draft_reminder_batch(self, batch_id: int):
    """Processes a draft reminder batch with crash-safe idempotency and privacy guarantees."""
    try:
        # Cross-event bootstrap lookup to identify the event
        with scopes_disabled():
            batch = DraftReminderBatch.all_objects.filter(pk=batch_id).first()
            if not batch:
                return
            event = batch.event

        with scope(event=event):
            with transaction.atomic():
                batch = (
                    DraftReminderBatch.objects
                    .select_for_update(skip_locked=True)
                    .filter(
                        pk=batch_id,
                        status__in=[
                            DraftReminderBatchStatus.PENDING,
                            DraftReminderBatchStatus.SENDING,
                        ],
                    )
                    .first()
                )
                if not batch:
                    return

                batch.status = DraftReminderBatchStatus.SENDING
                batch.save(update_fields=['status'])

            template = MailTemplate(
                event=event,
                subject=batch.subject,
                text=batch.text,
            )

            pending_recipient_ids = list(
                DraftReminderRecipient.objects
                .filter(batch=batch, status=DraftReminderRecipientStatus.PENDING)
                .values_list('pk', flat=True)
            )

            for recipient_id in pending_recipient_ids:
                should_retry = False
                # 1. Claim recipient and commit SENDING state to DB before SMTP network call
                with transaction.atomic():
                    b = DraftReminderBatch.objects.select_for_update().get(pk=batch_id)
                    if b.status != DraftReminderBatchStatus.SENDING:
                        return

                    recipient = (
                        DraftReminderRecipient.objects
                        .select_for_update(of=('self',), skip_locked=True)
                        .filter(batch=b, pk=recipient_id, status=DraftReminderRecipientStatus.PENDING)
                        .select_related('user')
                        .first()
                    )
                    if not recipient:
                        continue

                    sub = (
                        Submission.all_objects
                        .select_for_update()
                        .filter(pk=recipient.submission_id)
                        .first()
                    )
                    # Recheck submission state and speaker association atomically
                    if (
                        not sub
                        or sub.state != SubmissionStates.DRAFT
                        or not sub.speakers.filter(pk=recipient.user_id).exists()
                    ):
                        recipient.status = DraftReminderRecipientStatus.SKIPPED
                        recipient.save(update_fields=['status'])
                        DraftReminderBatch.objects.filter(pk=batch_id).update(
                            skipped_count=models.F('skipped_count') + 1
                        )
                        continue

                    # Prepare message before committing SENDING so template errors do not leave recipient in SENDING
                    mail = template.to_mail(
                        user=recipient.user,
                        event=event,
                        locale=sub.get_email_locale(recipient.user.locale),
                        context_kwargs={
                            'submission': sub,
                            'user': recipient.user,
                        },
                        skip_queue=False,
                        commit=False,
                    )

                    # Record SENDING intent and commit immediately before SMTP dispatch
                    recipient.status = DraftReminderRecipientStatus.SENDING
                    recipient.save(update_fields=['status'])

                # 2. Dispatch SMTP email outside the database lock
                try:
                    # Direct synchronous send within worker thread: sensitive=True redacts logs and exceptions
                    mail.send(synchronous=True, sensitive=True)
                except (SendMailException, SMTPException, OSError) as exc:
                    cause = getattr(exc, '__cause__', None) or exc
                    smtp_code = getattr(exc, 'smtp_code', None) or getattr(cause, 'smtp_code', None)
                    errno = getattr(exc, 'errno', None) or getattr(cause, 'errno', None)
                    is_retryable = (
                        (smtp_code in RETRY_SMTP_CODES or (isinstance(smtp_code, int) and 400 <= smtp_code < 500))
                        or errno in RETRY_ERRNOS
                    )
                    with transaction.atomic():
                        DraftReminderBatch.objects.select_for_update().filter(pk=batch_id).first()
                        if is_retryable:
                            recipient.status = DraftReminderRecipientStatus.PENDING
                            recipient.save(update_fields=['status'])
                            logger.warning(
                                '[DraftReminder] Transient transport error for recipient %s in batch %s: %s',
                                recipient.pk,
                                batch_id,
                                type(exc).__name__,
                            )
                            should_retry = True
                        else:
                            sanitized_err = f'{type(exc).__name__}: delivery failed'
                            recipient.status = DraftReminderRecipientStatus.FAILED
                            recipient.error = sanitized_err
                            recipient.save(update_fields=['status', 'error'])
                            DraftReminderBatch.objects.filter(pk=batch_id).update(
                                failed_count=models.F('failed_count') + 1
                            )
                            logger.warning(
                                '[DraftReminder] Permanent delivery failure for recipient %s in batch %s: %s',
                                recipient.pk,
                                batch_id,
                                sanitized_err,
                            )
                    if should_retry:
                        raise DraftReminderTransportError(
                            f'Transient mail transport failure encountered for batch {batch_id}'
                        ) from None
                    continue

                # 3. Confirm SENT delivery status
                with transaction.atomic():
                    DraftReminderBatch.objects.select_for_update().filter(pk=batch_id).first()
                    recipient.status = DraftReminderRecipientStatus.SENT
                    recipient.sent_at = now()
                    recipient.save(update_fields=['status', 'sent_at'])
                    DraftReminderBatch.objects.filter(pk=batch_id).update(
                        sent_count=models.F('sent_count') + 1
                    )

            with transaction.atomic():
                batch = DraftReminderBatch.objects.select_for_update().get(pk=batch_id)
                remaining_pending = DraftReminderRecipient.objects.filter(
                    batch=batch, status=DraftReminderRecipientStatus.PENDING
                ).count()

                # Finalize any interrupted SENDING recipients from prior crashes as SENT
                DraftReminderRecipient.objects.filter(
                    batch=batch, status=DraftReminderRecipientStatus.SENDING
                ).update(status=DraftReminderRecipientStatus.SENT, sent_at=now())

                actual_sent = max(
                    batch.sent_count,
                    DraftReminderRecipient.objects.filter(
                        batch=batch, status=DraftReminderRecipientStatus.SENT
                    ).count(),
                )
                actual_failed = DraftReminderRecipient.objects.filter(
                    batch=batch, status=DraftReminderRecipientStatus.FAILED
                ).count()
                actual_skipped = DraftReminderRecipient.objects.filter(
                    batch=batch, status=DraftReminderRecipientStatus.SKIPPED
                ).count()
                batch.sent_count = actual_sent
                batch.failed_count = actual_failed
                batch.skipped_count = actual_skipped

                if remaining_pending == 0:
                    if batch.sent_count > 0 or (batch.sent_count == 0 and batch.failed_count == 0):
                        batch.status = DraftReminderBatchStatus.COMPLETED
                    else:
                        batch.status = DraftReminderBatchStatus.FAILED
                    batch.completed_at = now()
                else:
                    batch.status = DraftReminderBatchStatus.FAILED

                batch.save(
                    update_fields=[
                        'status',
                        'completed_at',
                        'sent_count',
                        'failed_count',
                        'skipped_count',
                    ]
                )

            try:
                reconcile_draft_reminder_batch_allowance(batch)
            except Exception:
                logger.exception(
                    'Allowance reconciliation failed for batch %s; will remain eligible for cleanup retry',
                    batch_id,
                )

        outcome = OUTCOME_SUCCESS if batch.sent_count > 0 else OUTCOME_FAILURE
        log_event(
            'mail',
            'mail.draft_reminder_batch',
            outcome,
            event_id=event.pk,
            object_id=batch_id,
            recipient_count=batch.sent_count,
        )

    except Exception as exc:
        logger.exception('[DraftReminder] Unexpected error for batch %s: %s', batch_id, type(exc).__name__)
        try:
            if self.request.retries >= self.max_retries:
                raise MaxRetriesExceededError()
            self.retry(exc=exc, args=[batch_id])
        except MaxRetriesExceededError:
            with scopes_disabled():
                batch = DraftReminderBatch.all_objects.filter(pk=batch_id).first()
                event = batch.event if batch else None
            if batch and event:
                with scope(event=event):
                    with transaction.atomic():
                        batch = DraftReminderBatch.objects.select_for_update().filter(pk=batch_id).first()
                        if batch:
                            DraftReminderRecipient.objects.filter(
                                batch=batch,
                                status__in=[
                                    DraftReminderRecipientStatus.PENDING,
                                    DraftReminderRecipientStatus.SENDING,
                                ],
                            ).update(status=DraftReminderRecipientStatus.FAILED)
                            batch.status = DraftReminderBatchStatus.FAILED
                            batch.completed_at = now()
                            batch.failed_count = DraftReminderRecipient.objects.filter(
                                batch=batch, status=DraftReminderRecipientStatus.FAILED
                            ).count()
                            batch.save(update_fields=['status', 'completed_at', 'failed_count'])
                    try:
                        reconcile_draft_reminder_batch_allowance(batch)
                    except Exception:
                        logger.exception(
                            'Allowance reconciliation failed for exhausted batch %s; cleanup will retry',
                            batch_id,
                        )
            log_event('mail', 'mail.draft_reminder_batch', OUTCOME_FAILURE, error_code='retries_exhausted')
            logger.error('[DraftReminder] Max retries exceeded for batch ID %s', batch_id)
