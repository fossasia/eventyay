import uuid

from django.db import models
from django.utils.timezone import now


class DraftReminderBatchStatus(models.TextChoices):
    PENDING = 'pending'
    SENDING = 'sending'
    COMPLETED = 'completed'
    FAILED = 'failed'


class DraftReminderRecipientStatus(models.TextChoices):
    PENDING = 'pending'
    SENT = 'sent'
    FAILED = 'failed'


class DraftReminderBatch(models.Model):
    """Private batch tracker for draft-submission reminder emails.

    Not exposed through the visible outbox — exists solely for crash
    recovery, idempotency, and allowance reconciliation.  Rows are
    auto-purged by the cleanup management command after retention_hours.
    """

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='+',
    )
    template = models.ForeignKey(
        'MailTemplate',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )
    status = models.CharField(
        max_length=10,
        choices=DraftReminderBatchStatus.choices,
        default=DraftReminderBatchStatus.PENDING,
    )
    total_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=now)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'DraftReminderBatch({self.uuid}, {self.status})'


class DraftReminderRecipient(models.Model):
    """Per-recipient delivery state within a DraftReminderBatch.

    Stores FK references only — no email addresses as strings — to
    preserve draft-author privacy while enabling crash-safe resume.
    """

    batch = models.ForeignKey(
        DraftReminderBatch,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    submission = models.ForeignKey(
        'Submission',
        on_delete=models.CASCADE,
        related_name='+',
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='+',
    )
    status = models.CharField(
        max_length=10,
        choices=DraftReminderRecipientStatus.choices,
        default=DraftReminderRecipientStatus.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['batch', 'submission', 'user'],
                name='unique_draft_reminder_recipient',
            ),
        ]
