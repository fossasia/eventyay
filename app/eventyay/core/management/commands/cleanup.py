import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils.timezone import now

from eventyay.base.models import (
    DraftReminderBatch,
    DraftReminderBatchStatus,
    DraftReminderRecipient,
    DraftReminderRecipientStatus,
)
from eventyay.base.models.auth import ShortToken
from eventyay.base.models.event import EventView
from eventyay.base.models.room import AnonymousInvite, RoomView
from eventyay.base.models.storage_model import StoredFile
from eventyay.common.tasks import reconcile_draft_reminder_batch_allowance


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Perform cleanup tasks"

    def handle(self, *args, **options):
        self._cleanup_views()
        self._cleanup_files()
        self._cleanup_tokens()
        self._cleanup_draft_reminder_batches()

    def _cleanup_draft_reminder_batches(self):
        cutoff_retention = now() - timedelta(days=7)
        cutoff_abandoned = now() - timedelta(hours=24)

        # 1. Terminalize and reconcile abandoned batches older than 24 hours (Reviews 2, 7, 21)
        abandoned = DraftReminderBatch.objects.filter(
            reconciled=False,
            created_at__lt=cutoff_abandoned,
        )
        for batch in abandoned:
            try:
                with transaction.atomic():
                    b = DraftReminderBatch.objects.select_for_update().get(pk=batch.pk)
                    if b.status in [DraftReminderBatchStatus.PENDING, DraftReminderBatchStatus.SENDING]:
                        b.status = DraftReminderBatchStatus.FAILED
                        b.completed_at = now()
                        b.failed_count = b.total_count - b.sent_count - b.skipped_count
                        b.save(update_fields=['status', 'completed_at', 'failed_count'])
                        DraftReminderRecipient.objects.filter(
                            batch=b, status=DraftReminderRecipientStatus.PENDING
                        ).update(status=DraftReminderRecipientStatus.FAILED)
                    reconcile_draft_reminder_batch_allowance(b)
            except Exception:
                logger.exception('Failed to reconcile draft reminder batch %s during cleanup', batch.pk)

        # 2. Delete completed/failed batches older than retention window
        # ONLY if successfully reconciled (Reviews 6 & 22)
        DraftReminderBatch.objects.filter(
            status__in=[DraftReminderBatchStatus.COMPLETED, DraftReminderBatchStatus.FAILED],
            reconciled=True,
            created_at__lt=cutoff_retention,
        ).delete()

    def _cleanup_files(self):
        for f in StoredFile.objects.filter(expires__isnull=False, expires__lt=now()):
            if f.file:
                f.file.delete(False)
            f.delete()

    def _cleanup_views(self):
        # Reset RoomView objects that never "ended". In the unlikely event the session *is* still open, this will
        # *temporarily* break the statistics, but it will be auto-corrected as soon as ``end_view`` is properly
        # called.
        RoomView.objects.filter(
            end__isnull=True, start__lt=now() - timedelta(hours=6)
        ).update(end=F("start") + timedelta(hours=1))
        RoomView.objects.filter(
            end__isnull=False, room__event__config__track_room_views=False
        ).delete()

        EventView.objects.filter(
            end__isnull=True, start__lt=now() - timedelta(hours=24)
        ).update(end=F("start") + timedelta(hours=4))
        EventView.objects.filter(
            end__isnull=False, event__config__track_event_views=False
        ).delete()

    def _cleanup_tokens(self):
        ShortToken.objects.filter(expires__lte=now() - timedelta(days=90)).delete()
        AnonymousInvite.objects.filter(expires__lte=now() - timedelta(days=90)).delete()
