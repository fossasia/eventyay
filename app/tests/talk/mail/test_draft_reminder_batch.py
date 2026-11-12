from unittest.mock import patch

import pytest
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Submission, SubmissionStates
from eventyay.base.models.draft_reminder import (
    DraftReminderBatch,
    DraftReminderBatchStatus,
    DraftReminderRecipient,
    DraftReminderRecipientStatus,
)
from eventyay.common.tasks import send_draft_reminder_batch


def _make_draft_submission(event, speaker, title='Draft talk'):
    with scope(event=event):
        sub = Submission.objects.create(
            title=title,
            event=event,
            submission_type=event.cfp.default_type,
            content_locale='en',
            state=SubmissionStates.DRAFT,
        )
        sub.speakers.add(speaker)
        return sub


def _create_batch(event, submissions_and_speakers, template=None, created_by=None):
    from eventyay.base.models.mail import MailTemplate

    with scopes_disabled():
        if template is None:
            template = MailTemplate.objects.create(
                event=event,
                subject='Reminder',
                text='You have an unsubmitted draft.',
                is_auto_created=True,
            )
        batch = DraftReminderBatch.objects.create(
            event=event,
            template=template,
            total_count=len(submissions_and_speakers),
            created_by=created_by,
        )
        DraftReminderRecipient.objects.bulk_create([
            DraftReminderRecipient(batch=batch, submission=sub, user=user)
            for sub, user in submissions_and_speakers
        ])
    return batch


@pytest.mark.django_db
def test_batch_creation(event, speaker):
    sub = _make_draft_submission(event, speaker)
    batch = _create_batch(event, [(sub, speaker)])
    assert batch.status == DraftReminderBatchStatus.PENDING
    assert batch.total_count == 1
    assert batch.recipients.count() == 1


@pytest.mark.django_db
def test_batch_send_marks_recipients_sent(event, speaker, mail_template):
    sub = _make_draft_submission(event, speaker)
    batch = _create_batch(event, [(sub, speaker)])

    with patch('eventyay.common.tasks.transaction'):
        send_draft_reminder_batch(batch.pk)

    with scopes_disabled():
        batch.refresh_from_db()
        assert batch.status == DraftReminderBatchStatus.COMPLETED
        assert batch.completed_at is not None

        recipient = batch.recipients.first()
        assert recipient.status == DraftReminderRecipientStatus.SENT
        assert recipient.sent_at is not None


@pytest.mark.django_db
def test_batch_skip_already_sent_on_retry(event, speaker, mail_template):
    """Retrying a partially dispatched batch does not re-send to already-sent recipients."""
    sub = _make_draft_submission(event, speaker)
    batch = _create_batch(event, [(sub, speaker)])

    with scopes_disabled():
        recipient = batch.recipients.first()
        recipient.status = DraftReminderRecipientStatus.SENT
        recipient.sent_at = now()
        recipient.save()

    with patch('eventyay.base.models.mail.MailTemplate.to_mail') as mock_to_mail:
        send_draft_reminder_batch(batch.pk)
        mock_to_mail.assert_not_called()

    with scopes_disabled():
        batch.refresh_from_db()
        assert batch.status == DraftReminderBatchStatus.COMPLETED


@pytest.mark.django_db
def test_batch_recipient_failure_continues(event, speaker, other_speaker, mail_template):
    """A per-recipient SMTP failure marks that recipient failed but continues the batch."""
    sub1 = _make_draft_submission(event, speaker, title='Draft 1')
    sub2 = _make_draft_submission(event, other_speaker, title='Draft 2')
    batch = _create_batch(event, [(sub1, speaker), (sub2, other_speaker)])

    call_count = 0
    original_to_mail = mail_template.__class__.to_mail

    def side_effect(self, user, event, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception('SMTP connection refused')
        return original_to_mail(self, user, event, **kwargs)

    with patch.object(mail_template.__class__, 'to_mail', side_effect):
        send_draft_reminder_batch(batch.pk)

    with scopes_disabled():
        batch.refresh_from_db()
        recipients = list(batch.recipients.order_by('pk'))
        statuses = {r.status for r in recipients}
        assert DraftReminderRecipientStatus.FAILED in statuses
        assert DraftReminderRecipientStatus.SENT in statuses
        assert batch.status == DraftReminderBatchStatus.COMPLETED


@pytest.mark.django_db
def test_batch_unique_constraint(event, speaker):
    """Cannot add the same submission+user twice to a batch."""
    sub = _make_draft_submission(event, speaker)
    batch = _create_batch(event, [(sub, speaker)])

    from django.db import IntegrityError
    with pytest.raises(IntegrityError):
        DraftReminderRecipient.objects.create(
            batch=batch, submission=sub, user=speaker,
        )


@pytest.mark.django_db
def test_batch_locked_skip(event, speaker, mail_template):
    """A batch already picked up by another worker (locked) is skipped."""
    sub = _make_draft_submission(event, speaker)
    batch = _create_batch(event, [(sub, speaker)])
    batch.status = DraftReminderBatchStatus.COMPLETED
    batch.save()

    with patch('eventyay.base.models.mail.MailTemplate.to_mail') as mock_to_mail:
        send_draft_reminder_batch(batch.pk)
        mock_to_mail.assert_not_called()


@pytest.mark.django_db
def test_cleanup_purges_old_batches(event, speaker):
    from datetime import timedelta

    sub = _make_draft_submission(event, speaker)
    old_batch = _create_batch(event, [(sub, speaker)])
    with scopes_disabled():
        DraftReminderBatch.objects.filter(pk=old_batch.pk).update(
            created_at=now() - timedelta(hours=73)
        )
        recent_batch = _create_batch(event, [(sub, speaker)])

    from eventyay.core.management.commands.cleanup import Command
    Command()._cleanup_draft_reminder_batches()

    with scopes_disabled():
        assert not DraftReminderBatch.objects.filter(pk=old_batch.pk).exists()
        assert DraftReminderBatch.objects.filter(pk=recent_batch.pk).exists()
