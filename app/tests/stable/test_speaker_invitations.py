import pytest
from django.core import mail as djmail
from django_scopes import scope

from eventyay.base.models import (
    SpeakerInvitation,
    SpeakerInvitationMailStates,
    SpeakerInvitationStates,
    Submission,
    SubmissionType,
)
from eventyay.common.exceptions import SendMailException


@pytest.fixture
def submission(db, event, user):
    with scope(event=event):
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        submission = Submission.objects.create(
            title='A proposal that needs a second speaker',
            event=event,
            submission_type=submission_type,
            abstract='Abstract',
            content_locale='en',
        )
        submission.speakers.add(user)
        return submission


@pytest.mark.django_db
class TestOrganiserAddsSpeaker:
    def test_sends_immediately_and_marks_invitation_sent(self, event, submission):
        djmail.outbox = []
        with scope(event=event):
            speaker, invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe'
            )

            assert speaker.email == 'jane@example.net'
            assert invitation.status == SpeakerInvitationStates.PENDING
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert invitation.mail.sent is not None
            assert len(djmail.outbox) == 1
            assert djmail.outbox[0].to == ['jane@example.net']

    def test_unchecked_send_immediately_queues_in_outbox(self, event, submission):
        djmail.outbox = []
        with scope(event=event):
            _speaker, invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe', send_immediately=False
            )

            assert invitation.mail_state == SpeakerInvitationMailStates.QUEUED
            assert invitation.mail.sent is None
            assert not djmail.outbox

    def test_failed_delivery_keeps_speaker_and_records_failure(
        self, event, submission, monkeypatch
    ):
        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            speaker, invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe'
            )

            assert speaker in submission.speakers.all()
            assert invitation.status == SpeakerInvitationStates.PENDING
            assert invitation.mail_state == SpeakerInvitationMailStates.FAILED
            assert invitation.can_resend

    def test_duplicate_invitation_is_not_created_twice(self, event, submission):
        with scope(event=event):
            submission.add_speaker(email='jane@example.net', name='Jane Doe')
            submission.add_speaker(email='jane@example.net', name='Jane Doe')

            assert (
                SpeakerInvitation.objects.filter(
                    submission=submission, email='jane@example.net'
                ).count()
                == 1
            )

    def test_has_speaker_email_detects_existing_speaker(self, event, submission, user):
        with scope(event=event):
            assert submission.has_speaker_email(user.email)
            assert not submission.has_speaker_email('nobody@example.net')


@pytest.mark.django_db
class TestSubmitterInvitesSpeaker:
    def test_invitation_is_sent_immediately(self, event, submission, user):
        djmail.outbox = []
        with scope(event=event):
            invitations = submission.send_invite(to='jane@example.net', _from=user)

            assert len(invitations) == 1
            invitation = invitations[0]
            assert invitation.status == SpeakerInvitationStates.PENDING
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert len(djmail.outbox) == 1

    def test_invitation_mail_is_persisted(self, event, submission, user):
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)[0]

            assert invitation.mail.pk
            assert invitation.mail.sent is not None
            assert submission in invitation.mail.submissions.all()

    def test_failed_delivery_is_recorded(self, event, submission, user, monkeypatch):
        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)[0]

            assert invitation.mail_state == SpeakerInvitationMailStates.FAILED
            assert invitation.can_resend

    def test_invitation_to_several_addresses(self, event, submission, user):
        djmail.outbox = []
        with scope(event=event):
            invitations = submission.send_invite(
                to='jane@example.net,john@example.net', _from=user
            )

            assert len(invitations) == 2
            assert len(djmail.outbox) == 2


@pytest.mark.django_db
class TestInvitationLifecycle:
    def test_resend_reuses_the_invitation(self, event, submission, user, monkeypatch):
        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)[0]
            assert invitation.mail_state == SpeakerInvitationMailStates.FAILED

        monkeypatch.undo()
        djmail.outbox = []
        with scope(event=event):
            invitation.mail.sent = None
            invitation.mail.save(update_fields=['sent'])
            assert invitation.deliver(send_immediately=True) is True
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert (
                SpeakerInvitation.objects.filter(submission=submission).count() == 1
            )
            assert len(djmail.outbox) == 1

    def test_accept_marks_invitation_accepted(self, event, submission, user):
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)[0]
            assert invitation.is_pending

            invitation.accept()
            invitation.refresh_from_db()

            assert invitation.status == SpeakerInvitationStates.ACCEPTED
            assert invitation.accepted is not None
            assert not invitation.can_resend

    def test_queued_invitation_can_still_be_resent(self, event, submission):
        djmail.outbox = []
        with scope(event=event):
            _speaker, invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe', send_immediately=False
            )
            assert invitation.can_resend

            assert invitation.deliver(send_immediately=True) is True
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert len(djmail.outbox) == 1
