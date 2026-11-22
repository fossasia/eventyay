from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail as djmail
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Submission, SubmissionStates, SubmissionType, User
from eventyay.base.models.draft_reminder import (
    DraftReminderBatch,
    DraftReminderBatchStatus,
    DraftReminderRecipient,
    DraftReminderRecipientStatus,
)
from eventyay.base.models.mail import QueuedMail
from eventyay.common.tasks import (
    reconcile_draft_reminder_batch_allowance,
    send_draft_reminder_batch,
)
from eventyay.core.management.commands.cleanup import Command as CleanupCommand
from eventyay.orga.forms.mails import DraftRemindersForm


@pytest.fixture
def speaker_user(db):
    return User.objects.create_user(
        email='speaker@example.com',
        password='testpass123',
        fullname='Speaker User',
        locale='en',
    )


@pytest.fixture
def other_speaker(db):
    return User.objects.create_user(
        email='speaker2@example.com',
        password='testpass123',
        fullname='Second Speaker',
        locale='en',
    )


def make_draft_submission(event, speaker, title='Draft Talk'):
    with scope(event=event):
        sub_type = event.submission_types.first()
        if not sub_type:
            sub_type = SubmissionType.objects.create(event=event, name='Talk')
        sub = Submission.objects.create(
            event=event,
            title=title,
            submission_type=sub_type,
            state=SubmissionStates.DRAFT,
        )
        sub.speakers.add(speaker)
        return sub


@pytest.mark.django_db
def test_batch_creation_and_privacy_guarantee(event, speaker_user, user):
    """Batches and recipients must only store relational IDs, never plaintext emails or outbox rows."""
    sub = make_draft_submission(event, speaker_user)

    with scope(event=event):
        form = DraftRemindersForm(
            event=event,
            data={'subject_0': 'Reminder Subject', 'text_0': 'Please submit your talk {submission_title}.'},
        )
        assert form.is_valid()
        batch = form.save(created_by=user)

    assert batch is not None
    assert batch.status == DraftReminderBatchStatus.PENDING
    assert batch.total_count == 1
    assert str(batch.subject) == 'Reminder Subject'
    assert batch.created_by == user

    recipient = batch.recipients.first()
    assert recipient is not None
    assert recipient.submission == sub
    assert recipient.user == speaker_user
    assert recipient.status == DraftReminderRecipientStatus.PENDING
    assert DraftReminderRecipient.objects.filter(batch=batch).count() == 1
    # Ensure no plaintext email addresses are stored in recipient columns
    assert not hasattr(recipient, 'email')
    assert not hasattr(recipient, 'to')

    # Ensure no rows were added to the visible QueuedMail outbox
    with scopes_disabled():
        assert QueuedMail.objects.count() == 0


@pytest.mark.django_db
def test_batch_send_success_and_no_outbox_leak(event, speaker_user, user):
    """A batch task sends reminders directly without creating outbox rows and records completion."""
    make_draft_submission(event, speaker_user)

    with scope(event=event):
        form = DraftRemindersForm(
            event=event,
            data={'subject_0': 'Finish draft', 'text_0': 'Reminder for {submission_title}.'},
        )
        assert form.is_valid()
        batch = form.save(created_by=user)

    djmail.outbox = []
    send_draft_reminder_batch(batch.pk)

    with scopes_disabled():
        batch.refresh_from_db()
        assert batch.status == DraftReminderBatchStatus.COMPLETED
        assert batch.completed_at is not None
        assert batch.sent_count == 1
        assert batch.failed_count == 0
        assert batch.skipped_count == 0
        assert batch.reconciled is True

        recipient = batch.recipients.first()
        assert recipient.status == DraftReminderRecipientStatus.SENT
        assert recipient.sent_at is not None

        # Verify email was sent via SMTP
        assert len(djmail.outbox) == 1
        assert djmail.outbox[0].to == [speaker_user.email]

        # Verify privacy: no QueuedMail outbox records created
        assert QueuedMail.objects.count() == 0


@pytest.mark.django_db
def test_batch_skips_non_draft_submissions(event, speaker_user, other_speaker, user):
    """Submissions that are no longer in DRAFT state must be marked SKIPPED without sending."""
    sub1 = make_draft_submission(event, speaker_user, title='Still Draft')
    sub2 = make_draft_submission(event, other_speaker, title='Already Submitted')

    with scope(event=event):
        form = DraftRemindersForm(
            event=event,
            data={'subject_0': 'Reminder', 'text_0': 'Submit {submission_title}.'},
        )
        assert form.is_valid()
        batch = form.save(created_by=user)

        # Transition sub2 to SUBMITTED before batch runs
        sub2.state = SubmissionStates.SUBMITTED
        sub2.save()

    djmail.outbox = []
    send_draft_reminder_batch(batch.pk)

    with scopes_disabled():
        batch.refresh_from_db()
        assert batch.status == DraftReminderBatchStatus.COMPLETED
        assert batch.sent_count == 1
        assert batch.skipped_count == 1
        assert batch.failed_count == 0

        r1 = batch.recipients.get(submission=sub1)
        assert r1.status == DraftReminderRecipientStatus.SENT
        assert r1.sent_at is not None

        r2 = batch.recipients.get(submission=sub2)
        assert r2.status == DraftReminderRecipientStatus.SKIPPED
        assert r2.sent_at is None

        # Only 1 email was sent
        assert len(djmail.outbox) == 1
        assert djmail.outbox[0].to == [speaker_user.email]


@pytest.mark.django_db
def test_batch_crash_recovery_and_deduplication(event, speaker_user, other_speaker, user):
    """Re-executing an interrupted batch only sends remaining PENDING recipients without duplicate sends."""
    sub1 = make_draft_submission(event, speaker_user, title='Talk 1')
    sub2 = make_draft_submission(event, other_speaker, title='Talk 2')

    with scope(event=event):
        form = DraftRemindersForm(
            event=event,
            data={'subject_0': 'Reminder', 'text_0': 'Submit {submission_title}.'},
        )
        assert form.is_valid()
        batch = form.save(created_by=user)

    # Simulate an interruption: recipient 1 was already marked SENT before a worker crash
    with scopes_disabled():
        r1 = batch.recipients.get(submission=sub1)
        r1.status = DraftReminderRecipientStatus.SENT
        r1.sent_at = now()
        r1.save()
        batch.sent_count = 1
        batch.status = DraftReminderBatchStatus.SENDING
        batch.save()

    djmail.outbox = []
    # Resume the batch
    send_draft_reminder_batch(batch.pk)

    with scopes_disabled():
        batch.refresh_from_db()
        assert batch.status == DraftReminderBatchStatus.COMPLETED
        assert batch.sent_count == 2

        # Only recipient 2 was sent during this run (no duplicate for recipient 1)
        assert len(djmail.outbox) == 1
        assert djmail.outbox[0].to == [other_speaker.email]

        r2 = batch.recipients.get(submission=sub2)
        assert r2.status == DraftReminderRecipientStatus.SENT
        assert r2.sent_at is not None


@pytest.mark.django_db
def test_allowance_reconciliation_releases_unsent_quota(event, speaker_user, other_speaker, user):
    """Unsent allowance from skipped or failed reminders is released back to the organizer."""
    make_draft_submission(event, speaker_user, title='Draft 1')
    sub2 = make_draft_submission(event, other_speaker, title='Draft 2')

    with scope(event=event):
        form = DraftRemindersForm(
            event=event,
            data={'subject_0': 'Reminder', 'text_0': 'Submit {submission_title}.'},
        )
        assert form.is_valid()
        batch = form.save(created_by=user)

        # Transition sub2 so it is skipped
        sub2.state = SubmissionStates.SUBMITTED
        sub2.save()

    with patch('eventyay.common.tasks.record_usage') as mock_record:
        send_draft_reminder_batch(batch.pk)

        # Total was 2, sent was 1, skipped was 1 -> unsent is 1
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs['quantity'] == -1
        assert mock_record.call_args.kwargs['unit'] == 'emails'

    with scopes_disabled():
        batch.refresh_from_db()
        assert batch.reconciled is True

    # Re-running reconciliation on an already-reconciled batch is an idempotent no-op
    with patch('eventyay.common.tasks.record_usage') as mock_record2:
        reconcile_draft_reminder_batch_allowance(batch)
        mock_record2.assert_not_called()


@pytest.mark.django_db
def test_cleanup_draft_reminder_batches(event, user):
    """The cleanup command purges completed/failed batches older than retention, preserving pending batches."""
    with scopes_disabled():
        # Completed batch older than 7 days -> should be deleted
        b_old_completed = DraftReminderBatch.objects.create(
            event=event,
            subject='Old Completed',
            text='text',
            status=DraftReminderBatchStatus.COMPLETED,
            reconciled=True,
            created_at=now() - timedelta(days=8),
        )
        # Failed batch older than 7 days -> should be deleted
        b_old_failed = DraftReminderBatch.objects.create(
            event=event,
            subject='Old Failed',
            text='text',
            status=DraftReminderBatchStatus.FAILED,
            reconciled=True,
            created_at=now() - timedelta(days=8),
        )
        # Pending/sending batch older than 7 days (e.g. queue delay) -> should NOT be deleted
        b_old_pending = DraftReminderBatch.objects.create(
            event=event,
            subject='Old Pending',
            text='text',
            status=DraftReminderBatchStatus.PENDING,
            reconciled=True,
            created_at=now() - timedelta(days=8),
        )
        # Completed batch younger than 7 days -> should NOT be deleted
        b_recent_completed = DraftReminderBatch.objects.create(
            event=event,
            subject='Recent Completed',
            text='text',
            status=DraftReminderBatchStatus.COMPLETED,
            reconciled=True,
            created_at=now() - timedelta(days=2),
        )
        # Abandoned unreconciled batch older than 24h -> should be reconciled
        b_abandoned = DraftReminderBatch.objects.create(
            event=event,
            subject='Abandoned',
            text='text',
            status=DraftReminderBatchStatus.FAILED,
            total_count=5,
            sent_count=2,
            reconciled=False,
            created_at=now() - timedelta(hours=36),
        )

    with patch('eventyay.core.management.commands.cleanup.reconcile_draft_reminder_batch_allowance') as mock_reconcile:
        CleanupCommand().handle()
        mock_reconcile.assert_called_once_with(b_abandoned)

    with scopes_disabled():
        assert not DraftReminderBatch.objects.filter(pk=b_old_completed.pk).exists()
        assert not DraftReminderBatch.objects.filter(pk=b_old_failed.pk).exists()
        assert DraftReminderBatch.objects.filter(pk=b_old_pending.pk).exists()
        assert DraftReminderBatch.objects.filter(pk=b_recent_completed.pk).exists()
        assert DraftReminderBatch.objects.filter(pk=b_abandoned.pk).exists()
