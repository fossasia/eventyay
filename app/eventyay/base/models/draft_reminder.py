import uuid

from django.db import models
from django.utils.timezone import now
from django_scopes import ScopedManager
from i18nfield.fields import I18nCharField, I18nTextField


class DraftReminderBatchStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENDING = 'sending', 'Sending'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class DraftReminderRecipientStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SENDING = 'sending', 'Sending'
    SENT = 'sent', 'Sent'
    FAILED = 'failed', 'Failed'
    SKIPPED = 'skipped', 'Skipped'


class DraftReminderBatch(models.Model):
    """Private batch tracker for draft-submission reminder emails.

    Not exposed through the visible outbox or public mail history — exists solely
    for crash recovery, idempotency, and allowance reconciliation. Rows are
    purged by the cleanup management command once completed or failed.
    """

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event = models.ForeignKey(
        'Event',
        on_delete=models.CASCADE,
        related_name='+',
    )
    subject = I18nCharField(max_length=200)
    text = I18nTextField()
    status = models.CharField(
        max_length=10,
        choices=DraftReminderBatchStatus.choices,
        default=DraftReminderBatchStatus.PENDING,
    )
    total_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    reconciled = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=now)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    objects = ScopedManager(event='event')
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'DraftReminderBatch({self.uuid}, {self.status})'


class DraftReminderRecipient(models.Model):
    """Per-recipient delivery state within a DraftReminderBatch.

    Stores foreign key references only (submission and speaker User) — never
    plaintext email strings or rendered messages — preserving draft-author
    privacy while allowing crash-safe resumption.
    """

    batch = models.ForeignKey(
        DraftReminderBatch,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    submission = models.ForeignKey(
        'Submission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    status = models.CharField(
        max_length=10,
        choices=DraftReminderRecipientStatus.choices,
        default=DraftReminderRecipientStatus.PENDING,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default='')

    objects = ScopedManager(event='batch__event')
    all_objects = models.Manager()

    class Meta:
        unique_together = [('batch', 'submission', 'user')]

    def __str__(self):
        return f'DraftReminderRecipient({self.batch_id}, sub={self.submission_id}, user={self.user_id}, {self.status})'
