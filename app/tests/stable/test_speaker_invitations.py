from unittest import mock

import pytest
from django.conf import settings
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core import mail as djmail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import override_settings
from django_scopes import scope

from eventyay.base.models import (
    Event,
    Organizer,
    QueuedMail,
    SpeakerInvitation,
    SpeakerInvitationMailStates,
    SpeakerInvitationStates,
    Submission,
    SubmissionType,
)
from eventyay.base.models import User as BaseUser
from eventyay.base.services.speaker_invite_limits import (
    get_invitation_resend_key,
    get_user_rate_limit_key,
    record_speaker_invite_send,
    validate_speaker_invite_rate_limit,
)
from eventyay.cfp.flow import ProfileStep
from eventyay.cfp.forms.submissions import SubmissionInvitationForm
from eventyay.cfp.views.auth import RecoverView
from eventyay.cfp.views.user import (
    SubmissionInviteAcceptView,
    SubmissionInviteResendView,
    SubmissionInviteView,
    SubmissionsEditView,
)
from eventyay.common.exceptions import SendMailException
from eventyay.common.text.phrases import phrases


LOCMEM_CACHE = {
    **settings.CACHES,
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-speaker-invitations',
    }
}


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
            invitation = submission.send_invite(to='jane@example.net', _from=user)

            assert invitation.status == SpeakerInvitationStates.PENDING
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert len(djmail.outbox) == 1

    def test_invitation_mail_is_persisted(self, event, submission, user):
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)

            assert invitation.mail.pk
            assert invitation.mail.sent is not None
            assert submission in invitation.mail.submissions.all()

    def test_form_ignores_custom_subject_and_text(self, event, submission, user):
        from eventyay.cfp.forms.submissions import SubmissionInvitationForm

        with scope(event=event):
            form = SubmissionInvitationForm(
                submission=submission,
                speaker=user,
                data={'speaker': 'jane@example.net', 'subject': 'Buy now', 'text': 'Spam'},
            )
            assert form.is_valid()
            mail = form.save().mail

            assert 'Buy now' not in mail.subject
            assert 'Spam' not in mail.text
            assert submission.urls.accept_invitation.full() in mail.text

    def test_failed_delivery_is_recorded(self, event, submission, user, monkeypatch):
        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)

            assert invitation.mail_state == SpeakerInvitationMailStates.FAILED
            assert invitation.can_resend


@pytest.mark.django_db
class TestInvitationLifecycle:
    def test_resend_reuses_the_invitation(self, event, submission, user, monkeypatch):
        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)
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
            invitation = submission.send_invite(to='jane@example.net', _from=user)
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


@pytest.mark.django_db
class TestInvitationIdentity:
    def test_email_is_normalised(self, event, submission, user):
        with scope(event=event):
            invitation = submission.send_invite(to='Jane@Example.NET', _from=user)

            assert invitation.email == 'jane@example.net'

    def test_case_variants_reuse_one_invitation(self, event, submission, user):
        djmail.outbox = []
        with scope(event=event):
            submission.send_invite(to='Jane@Example.NET', _from=user)
            submission.send_invite(to='jane@example.net', _from=user)

            assert SpeakerInvitation.objects.filter(submission=submission).count() == 1
            assert len(djmail.outbox) == 1

    def test_repeated_add_speaker_does_not_resend(self, event, submission):
        djmail.outbox = []
        with scope(event=event):
            submission.add_speaker(email='jane@example.net', name='Jane Doe')
            submission.add_speaker(email='JANE@example.net', name='Jane Doe')

            assert SpeakerInvitation.objects.filter(submission=submission).count() == 1
            assert len(djmail.outbox) == 1

    def test_accepted_invitation_cannot_be_resent(self, event, submission, user):
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)
            invitation.accept()

            assert not invitation.can_resend

    def test_sent_invitation_is_resent_as_a_new_mail(self, event, submission, user):
        djmail.outbox = []
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)
            first_mail = invitation.mail
            assert invitation.can_resend

            assert invitation.resend(requestor=user) is True

            invitation.refresh_from_db()
            first_mail.refresh_from_db()
            assert invitation.mail != first_mail
            assert first_mail.sent is not None
            assert invitation.mail.sent is not None
            assert submission in invitation.mail.submissions.all()
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert len(djmail.outbox) == 2

    def test_failed_invitation_is_resent_with_the_same_mail(
        self, event, submission, user, monkeypatch
    ):
        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)
            first_mail = invitation.mail

        monkeypatch.undo()
        djmail.outbox = []
        with scope(event=event):
            assert invitation.resend(requestor=user) is True
            assert invitation.mail == first_mail
            assert len(djmail.outbox) == 1

    def test_outbox_send_marks_invitation_sent(self, event, submission):
        with scope(event=event):
            _speaker, invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe', send_immediately=False
            )
            assert invitation.mail_state == SpeakerInvitationMailStates.QUEUED

            invitation.mail.send()
            invitation.refresh_from_db()

            assert invitation.mail_state == SpeakerInvitationMailStates.SENT

    def test_outbox_send_after_failure_marks_invitation_sent(
        self, event, submission, user, monkeypatch
    ):
        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)
            assert invitation.mail_state == SpeakerInvitationMailStates.FAILED

        monkeypatch.undo()
        with scope(event=event):
            invitation.mail.send()
            invitation.refresh_from_db()

            assert invitation.mail_state == SpeakerInvitationMailStates.SENT

    def test_deliver_on_sent_mail_does_not_raise(self, event, submission):
        with scope(event=event):
            _speaker, invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe'
            )

            assert invitation.deliver(send_immediately=True) is True
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT


@pytest.mark.django_db
class TestInvitationAcceptance:
    def test_only_the_matching_invitation_is_accepted(self, event, submission, user, rf):
        from django.contrib.messages.storage.fallback import FallbackStorage

        from eventyay.cfp.views.user import SubmissionInviteAcceptView

        with scope(event=event):
            mine = SpeakerInvitation.objects.create(
                submission=submission, email=user.email
            )
            someone_else = SpeakerInvitation.objects.create(
                submission=submission, email='other@example.net'
            )

            request = rf.post('/')
            request.user = user
            request.event = event
            request.session = {}
            request._messages = FallbackStorage(request)

            view = SubmissionInviteAcceptView()
            view.request = request
            view.kwargs = {'code': submission.code}
            view.post(request, code=submission.code)

            mine.refresh_from_db()
            someone_else.refresh_from_db()

        assert mine.status == SpeakerInvitationStates.ACCEPTED
        assert mine.user == user
        assert someone_else.status == SpeakerInvitationStates.PENDING
        assert someone_else.user is None


@pytest.mark.django_db
class TestRevokeInvitation:
    def test_revoke_removes_invitation(self, event, submission, user):
        with scope(event=event):
            invitation = submission.send_invite(to='jane@example.net', _from=user)
            sent_mail = invitation.mail

            invitation.revoke(person=user)

            assert not SpeakerInvitation.objects.filter(pk=invitation.pk).exists()
            assert QueuedMail.objects.filter(pk=sent_mail.pk).exists()
            assert not submission.has_speaker_email('jane@example.net')

    def test_revoke_deletes_unsent_mail(self, event, submission):
        with scope(event=event):
            _speaker, invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe', send_immediately=False
            )
            queued_mail = invitation.mail

            invitation.revoke()

            assert not QueuedMail.objects.filter(pk=queued_mail.pk).exists()

    def test_revoked_address_can_be_invited_again(self, event, submission, user):
        djmail.outbox = []
        with scope(event=event):
            submission.send_invite(to='jane@example.net', _from=user).revoke()

            invitation = submission.send_invite(to='jane@example.net', _from=user)

            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert len(djmail.outbox) == 2

    def test_removed_speaker_can_be_added_again(self, event, submission):
        djmail.outbox = []
        with scope(event=event):
            speaker, _invitation = submission.add_speaker(
                email='jane@example.net', name='Jane Doe'
            )
            submission.remove_speaker(speaker)

            assert not SpeakerInvitation.objects.filter(submission=submission).exists()
            assert not submission.has_speaker_email('jane@example.net')

            submission.add_speaker(email='jane@example.net', name='Jane Doe')
            assert len(djmail.outbox) == 2


@pytest.mark.django_db
class TestSubmitterInviteView:
    def test_failed_invite_redirects_to_the_proposal(
        self, event, submission, user, rf, monkeypatch
    ):
        from django.contrib.messages import get_messages
        from django.contrib.messages.storage.fallback import FallbackStorage

        from eventyay.cfp.forms.submissions import SubmissionInvitationForm
        from eventyay.cfp.views.user import SubmissionInviteView

        def explode(*args, **kwargs):
            raise SendMailException('backend is down')

        monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
        with scope(event=event):
            request = rf.post('/')
            request.user = user
            request.event = event
            request.session = {}
            request._messages = FallbackStorage(request)

            view = SubmissionInviteView()
            view.request = request
            view.kwargs = {'code': submission.code}
            form = SubmissionInvitationForm(
                submission=submission,
                speaker=user,
                data={'speaker': 'jane@example.net'},
            )
            assert form.is_valid()

            response = view.form_valid(form)

            assert response.status_code == 302
            assert response.url == submission.urls.user_base
            invitation = SpeakerInvitation.objects.get(submission=submission)
            assert invitation.mail_state == SpeakerInvitationMailStates.FAILED
            assert invitation.can_resend
            assert any(
                'jane@example.net' in str(message) for message in get_messages(request)
            )


@pytest.mark.django_db
class TestOrganiserSpeakersFragment:
    def test_fragment_after_adding_speaker_has_no_form_errors(
        self, client, event, submission, user, team
    ):
        team.can_change_submissions = True
        team.is_reviewer = False
        team.save()
        client.force_login(user)
        with scope(event=event):
            url = submission.orga_urls.speakers

        response = client.post(
            url,
            {
                'email': 'jane@example.net',
                'name': 'Jane Doe',
                'biography': 'Speaks about open source.',
                'send_immediately': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        assert response.status_code == 200
        html = response.json()['html']
        assert 'already been added or invited' not in html
        assert 'is-invalid' not in html


@pytest.mark.django_db
class TestCoSpeakerInviteHardening:
    def test_form_only_contains_speaker_field(self, submission, user):
        form = SubmissionInvitationForm(submission=submission, speaker=user)
        assert list(form.fields.keys()) == ['speaker']
        assert 'subject' not in form.fields
        assert 'text' not in form.fields

    def test_form_accepts_single_valid_email(self, event, submission, user):
        with scope(event=event):
            form = SubmissionInvitationForm(
                submission=submission,
                speaker=user,
                data={'speaker': 'valid@example.org'},
            )
            assert form.is_valid()
            assert form.cleaned_data['speaker'] == 'valid@example.org'

    def test_form_rejects_multiple_emails(self, event, submission, user):
        with scope(event=event):
            for invalid_input in [
                'first@example.org, second@example.org',
                'first@example.org; second@example.org',
                'first@example.org second@example.org',
            ]:
                form = SubmissionInvitationForm(
                    submission=submission,
                    speaker=user,
                    data={'speaker': invalid_input},
                )
                assert not form.is_valid()
                assert 'speaker' in form.errors

    def test_form_rejects_existing_speaker_or_invited(self, event, submission, user):
        with scope(event=event):
            form = SubmissionInvitationForm(
                submission=submission,
                speaker=user,
                data={'speaker': user.email},
            )
            assert not form.is_valid()
            assert 'already been added or invited' in str(form.errors['speaker'])

    def test_form_save_uses_standard_invitation_template(self, event, submission, user):
        djmail.outbox = []
        with scope(event=event):
            form = SubmissionInvitationForm(
                submission=submission,
                speaker=user,
                data={'speaker': 'partner@example.org'},
            )
            assert form.is_valid()
            invitation = form.save()
            assert invitation.status == SpeakerInvitationStates.PENDING
            assert invitation.mail_state == SpeakerInvitationMailStates.SENT
            assert len(djmail.outbox) == 1
            outbound = djmail.outbox[0]
            assert outbound.to == ['partner@example.org']
            expected_subject = phrases.cfp.invite_subject.format(speaker=user.get_display_name())
            expected_body = phrases.cfp.invite_text.format(
                event=submission.event.name,
                title=submission.title,
                url=submission.urls.accept_invitation.full(),
                speaker=user.get_display_name(),
            )
            assert expected_subject in outbound.subject
            assert outbound.body == expected_body

    def test_co_speaker_counting_and_cap(self, event, submission, user):
        with scope(event=event):
            assert submission.confirmed_co_speakers_count == 0
            assert submission.pending_invitations_count == 0
            assert submission.co_speaker_count == 0
            assert submission.can_invite_co_speakers is True

            for i in range(10):
                SpeakerInvitation.objects.create(
                    submission=submission,
                    email=f'cospeaker{i}@example.org',
                    invited_by=user,
                )

            assert submission.confirmed_co_speakers_count == 0
            assert submission.pending_invitations_count == 10
            assert submission.co_speaker_count == 10
            assert submission.can_invite_co_speakers is False

            form = SubmissionInvitationForm(
                submission=submission,
                speaker=user,
                data={'speaker': 'eleventh@example.org'},
            )
            assert not form.is_valid()
            assert 'maximum of 10 co-speakers' in str(form.errors)

            invitation_to_revoke = submission.speaker_invitations.first()
            invitation_to_revoke.revoke(person=user)

            assert submission.pending_invitations_count == 9
            assert submission.co_speaker_count == 9
            assert submission.can_invite_co_speakers is True

            form = SubmissionInvitationForm(
                submission=submission,
                speaker=user,
                data={'speaker': 'eleventh@example.org'},
            )
            assert form.is_valid()

    def test_invite_view_at_limit_shows_message_and_keeps_link_box(self, event, submission, user, rf):
        with scope(event=event):
            for i in range(10):
                SpeakerInvitation.objects.create(
                    submission=submission,
                    email=f'pending{i}@example.org',
                    invited_by=user,
                )

            request = rf.get('/')
            request.user = user
            request.event = event
            request.session = SessionStore()
            request.LANGUAGE_CODE = 'en'

            view = SubmissionInviteView()
            view.request = request
            view.kwargs = {'code': submission.code}
            response = view.get(request, code=submission.code)
            assert response.status_code == 200
            assert response.context_data['can_invite_co_speakers'] is False
            rendered = response.render().content.decode()
            assert 'maximum of 10 co-speakers' in rendered
            assert submission.urls.accept_invitation.full() in rendered
            assert 'name="speaker"' not in rendered

    def test_organizer_area_uncapped(self, event, submission, user):
        with scope(event=event):
            for i in range(10):
                SpeakerInvitation.objects.create(
                    submission=submission,
                    email=f'pending{i}@example.org',
                    invited_by=user,
                )
            assert not submission.can_invite_co_speakers

            speaker, invitation = submission.add_speaker(email='eleventh@example.org', name='Eleventh Speaker')
            assert speaker in submission.speakers.all()
            assert invitation.email == 'eleventh@example.org'
            assert submission.speakers.count() == 2

    def test_accept_invitation_cap_checks(self, event, submission, user, rf):
        with scope(event=event):
            invited_user = BaseUser.objects.create_user(email='invited@example.org', password='password123')
            invitation = SpeakerInvitation.objects.create(
                submission=submission,
                email=invited_user.email,
                invited_by=user,
            )

            # Invited user accepts when under limit
            req = rf.post('/')
            req.user = invited_user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            response = view.post(req, code=submission.code, invitation=submission.invitation_token)
            assert response.status_code == 302
            invitation.refresh_from_db()
            assert invitation.status == SpeakerInvitationStates.ACCEPTED
            assert invited_user in submission.speakers.all()

            # Now add 9 more co-speakers so confirmed co-speakers reaches 10 (11 total speakers)
            for i in range(9):
                extra_user = BaseUser.objects.create_user(email=f'extra{i}@example.org', password='password123')
                submission.speakers.add(extra_user)

            assert submission.confirmed_co_speakers_count == 10
            twelfth_user = BaseUser.objects.create_user(email='twelfth@example.org', password='password123')

            # 12th user visits accept page (GET)
            get_req = rf.get('/')
            get_req.user = twelfth_user
            get_req.event = event
            get_req.session = SessionStore()
            get_req._messages = FallbackStorage(get_req)
            get_req.LANGUAGE_CODE = 'en'

            get_view = SubmissionInviteAcceptView()
            get_view.request = get_req
            get_view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            get_resp = get_view.get(get_req, code=submission.code, invitation=submission.invitation_token)
            assert get_resp.status_code == 200
            rendered = get_resp.render().content.decode()
            assert 'reached the maximum of 10 co-speakers' in rendered

            # 12th user attempts to accept (POST)
            post_req = rf.post('/')
            post_req.user = twelfth_user
            post_req.event = event
            post_req.session = SessionStore()
            post_req._messages = FallbackStorage(post_req)
            post_req.LANGUAGE_CODE = 'en'

            post_view = SubmissionInviteAcceptView()
            post_view.request = post_req
            post_view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            post_resp = post_view.post(post_req, code=submission.code, invitation=submission.invitation_token)
            assert post_resp.status_code == 302
            assert twelfth_user not in submission.speakers.all()

    def test_wizard_profile_step_handles_cap_overflow(self, event, user, rf):
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name='Talk')
            sub = Submission.objects.create(
                title='Wizard Submission',
                event=event,
                submission_type=sub_type,
            )
            sub.speakers.add(user)

            for i in range(10):
                SpeakerInvitation.objects.create(
                    submission=sub,
                    email=f'wizard_pending{i}@example.org',
                    invited_by=user,
                )
            assert not sub.can_invite_co_speakers

            req = rf.post('/', {'additional_speaker': 'overflow_wizard@example.org'})
            req.user = user
            req.event = event
            req.submission = sub
            req.session = SessionStore()
            req._messages = FallbackStorage(req)

            step = ProfileStep(event=event)
            step.cfp_session = {'data': {}}
            form_mock = type('FormMock', (), {
                'cleaned_data': {'additional_speaker': 'overflow_wizard@example.org'},
                'user': None,
                'save': lambda *args, **kwargs: None,
                'is_valid': lambda *args, **kwargs: True,
            })()
            step.get_form = lambda from_storage=True: form_mock
            step.done(req, draft=False)
            messages = list(get_messages(req))
            assert any('maximum of 10 co-speakers' in str(m) for m in messages)

    def test_user_submission_edit_ui_at_limit(self, event, submission, user, rf):
        with scope(event=event):
            for i in range(10):
                SpeakerInvitation.objects.create(
                    submission=submission,
                    email=f'pending_edit{i}@example.org',
                    invited_by=user,
                )
            req = rf.get('/')
            req.user = user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionsEditView()
            view.request = req
            view.kwargs = {'code': submission.code}
            resp = view.get(req, code=submission.code)
            assert resp.status_code == 200
            content = resp.render().content.decode()
            assert 'reached the maximum of 10 co-speakers' in content
            assert 'class="add-speaker"' not in content

    def test_submission_send_invite_enforces_cap_and_lock(self, event, submission, user):
        with scope(event=event):
            # Reach the limit
            for i in range(10):
                SpeakerInvitation.objects.create(
                    submission=submission,
                    email=f'pending{i}@example.org',
                    invited_by=user,
                )

            assert submission.co_speaker_count == 10
            assert submission.can_invite_co_speakers is False

            # Calling send_invite directly on model raises ValidationError
            with pytest.raises(ValidationError):
                submission.send_invite(to='eleventh@example.org', _from=user)

    def test_send_invite_concurrency_idempotence(self, event, submission, user):
        djmail.outbox = []
        with scope(event=event):
            first = submission.send_invite(to='concurrent@example.org', _from=user)
            mail_count = QueuedMail.objects.filter(submissions=submission).count()

            # Calling send_invite again for the same address does not create duplicate mail
            second = submission.send_invite(to='concurrent@example.org', _from=user)
            assert first.pk == second.pk
            assert QueuedMail.objects.filter(submissions=submission).count() == mail_count

    def test_accepted_invitation_not_yet_speaker_counts_and_organizer_speakers_uncapped_on_recover(
        self, event, submission, user, rf
    ):
        with scope(event=event):
            invited_user = BaseUser.objects.create_user(email='recovered@example.org', password='oldpassword')
            invitation = SpeakerInvitation.objects.create(
                submission=submission,
                email=invited_user.email,
                user=invited_user,
                invited_by=user,
            )

            # Accept without adding to speakers (e.g. manually or via older flow)
            invitation.accept(user=invited_user)
            # Pending count still reflects accepted invites not yet in submission.speakers
            assert submission.pending_invitations_count == 1
            assert submission.co_speaker_count == 1

            # Organizer adds 11 more speakers (total 12 speakers on proposal: 1 submitter + 11 added)
            for i in range(11):
                submission.add_speaker(email=f'orgaspeaker{i}@example.org', name=f'Speaker {i}')
            assert submission.speakers.count() == 12

            # RecoverView for an organizer-added speaker (exceeding 10) completes password reset without error
            late_speaker = BaseUser.objects.get(email='orgaspeaker10@example.org')
            req = rf.post('/')
            req.user = late_speaker
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = RecoverView()
            view.request = req
            view.user = late_speaker
            form_mock = type('FormMock', (), {'cleaned_data': {'password': 'newpassword123'}})()
            view.form_valid(form_mock)
            late_invite = SpeakerInvitation.objects.get(submission=submission, email=late_speaker.email)
            assert late_invite.status == SpeakerInvitationStates.ACCEPTED

    def test_deny_reason_limit_vs_permission(self, event, submission, user, rf):
        with scope(event=event):
            # Fill 10 co-speakers
            for i in range(10):
                extra_user = BaseUser.objects.create_user(email=f'extra_co{i}@example.org', password='password123')
                submission.speakers.add(extra_user)

            other_user = BaseUser.objects.create_user(email='other@example.org', password='password123')

            req = rf.get('/')
            req.user = other_user
            req.event = event
            req.session = SessionStore()
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            assert view.deny_reason == 'limit'
            assert view.can_accept_invite is False

    def test_confirmed_speaker_with_pending_invite_not_double_counted(self, event, submission, user):
        with scope(event=event):
            co_user = BaseUser.objects.create_user(email='co@example.org', password='password123')
            submission.speakers.add(co_user)
            SpeakerInvitation.objects.create(
                submission=submission,
                email=co_user.email,
                user=co_user,
                invited_by=user,
            )
            assert submission.confirmed_co_speakers_count == 1
            assert submission.pending_invitations_count == 0
            assert submission.co_speaker_count == 1

    def test_send_invite_includes_accepted_invitations_in_capacity_check(self, event, submission, user):
        """Test that invitations in ACCEPTED state are counted and prevent double counting."""
        with scope(event=event):
            # Create an accepted invitation for a co-speaker
            co_user = BaseUser.objects.create_user(email='accepted_co@example.org', password='password123')
            inv = SpeakerInvitation.objects.create(
                submission=submission,
                email=co_user.email,
                user=co_user,
                invited_by=user,
                status=SpeakerInvitationStates.ACCEPTED,
            )
            # send_invite for the same address does not double count towards new_count
            assert submission.send_invite(to=co_user.email, _from=user).pk == inv.pk

    def test_accept_invitation_with_accepted_state_not_blocked_by_capacity(self, event, submission, user, rf):
        """Test that an invitation in ACCEPTED state is not blocked by capacity check if count reaches 10."""
        with scope(event=event):
            co_user = BaseUser.objects.create_user(email='co_accepted@example.org', password='password123')
            # Fill other 9 seats
            for i in range(9):
                other_user = BaseUser.objects.create_user(email=f'other{i}@example.org', password='password123')
                submission.speakers.add(other_user)

            assert submission.confirmed_co_speakers_count == 9

            # Create an accepted invitation for co_user
            SpeakerInvitation.objects.create(
                submission=submission,
                email=co_user.email,
                user=co_user,
                invited_by=user,
                status=SpeakerInvitationStates.ACCEPTED,
            )
            assert submission.co_speaker_count == 10

            req = rf.get('/')
            req.user = co_user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            # Should NOT be blocked with 'limit' because the user's invitation is already active/accepted
            assert view.deny_reason != 'limit'

    def test_invited_user_can_accept_after_organizers_exceed_cap(self, event, submission, user, rf):
        with scope(event=event):
            invitee = BaseUser.objects.create_user(email='invitee@example.org', password='password123')
            SpeakerInvitation.objects.create(submission=submission, email=invitee.email, invited_by=user)
            # Organizers are uncapped and add speakers past the limit
            for i in range(10):
                submission.speakers.add(
                    BaseUser.objects.create_user(email=f'orga_added{i}@example.org', password='password123')
                )
            assert submission.co_speaker_count > submission.MAX_CO_SPEAKERS

            req = rf.post('/')
            req.user = invitee
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            assert view.deny_reason is None
            view.post(req, code=submission.code, invitation=submission.invitation_token)
            assert invitee in submission.speakers.all()

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_resend_cap_enforced_at_max_resends(self, event, submission, user, rf):
        cache.clear()
        with scope(event=event):
            inv = submission.send_invite(to='resend_test@example.org', _from=user)
            assert inv.resend_count == 0
            assert inv.can_resend is True

            # 3 successful resends
            for i in range(3):
                assert inv.can_resend is True
                success = inv.resend(requestor=user, orga=False)
                assert success is True
                assert inv.resend_count == i + 1

            assert inv.resend_count == 3
            assert inv.can_resend is False

            # 4th resend via model is refused
            with pytest.raises(ValidationError, match='maximum of 3 times'):
                inv.resend(requestor=user, orga=False)

            # 4th resend via View returns warning message with dynamic count
            req = rf.post('/')
            req.user = user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteResendView()
            view.request = req
            view.kwargs = {'code': submission.code, 'pk': inv.pk}
            resp = view.post(req, code=submission.code, pk=inv.pk)
            assert resp.status_code == 302
            messages = list(get_messages(req))
            assert any('maximum of 3 times' in str(m) for m in messages)

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_failed_resend_is_not_counted(self, event, submission, user, monkeypatch):
        cache.clear()
        with scope(event=event):
            inv = submission.send_invite(to='fail_resend@example.org', _from=user)
            assert inv.resend_count == 0

            # Simulate mail server failure
            def explode(*args, **kwargs):
                raise SendMailException('mail server rejected')

            monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)
            assert inv.resend(requestor=user, orga=False) is False
            # Failed deliveries do not use up the resend limit
            assert inv.resend_count == 0

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_resend_view_reports_delivery_failure_on_last_resend(self, event, submission, user, rf, monkeypatch):
        cache.clear()
        with scope(event=event):
            inv = submission.send_invite(to='last_resend@example.org', _from=user)
            cache.set(get_invitation_resend_key(inv), inv.MAX_RESENDS - 1)

            def explode(*args, **kwargs):
                raise SendMailException('mail server down')

            monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)

            req = rf.post('/')
            req.user = user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteResendView()
            view.request = req
            view.kwargs = {'code': submission.code, 'pk': inv.pk}
            view.post(req, code=submission.code, pk=inv.pk)
            messages = [str(m) for m in get_messages(req)]
            assert any('could not be sent' in m for m in messages)
            assert not any('maximum of' in m for m in messages)
            assert inv.can_resend

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_organizer_resend_uncapped(self, event, submission, user):
        cache.clear()
        with scope(event=event):
            inv = submission.send_invite(to='orga_resend@example.org', _from=user)
            cache.set(get_invitation_resend_key(inv), 5)

            assert inv.can_resend is False
            assert inv.can_resend_orga is True

            # Orga resend succeeds even with resend_count >= 3
            assert inv.resend(requestor=user, orga=True) is True

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_hourly_rate_limit_per_user(self, event, submission, user):
        cache.clear()
        with scope(event=event):
            # Send 20 invitations (the limit)
            for i in range(20):
                sub = Submission.objects.create(
                    event=event,
                    title=f'Test Talk {i}',
                    submission_type=submission.submission_type,
                )
                sub.speakers.add(user)
                validate_speaker_invite_rate_limit(user)
                sub.send_invite(to=f'ratelimit{i}@example.org', _from=user)

            with pytest.raises(ValidationError, match='maximum number of invitations'):
                validate_speaker_invite_rate_limit(user)

            # 21st send attempt raises ValidationError
            sub21 = Submission.objects.create(
                event=event,
                title='Test Talk 21',
                submission_type=submission.submission_type,
            )
            sub21.speakers.add(user)
            with pytest.raises(ValidationError) as exc:
                sub21.send_invite(to='ratelimit21@example.org', _from=user)
            assert 'maximum number of invitations for now' in str(exc.value)

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_hourly_rate_limit_counts_attempts_even_on_failure(self, event, submission, user, monkeypatch):
        cache.clear()
        with scope(event=event):
            monkeypatch.setattr(
                SpeakerInvitation,
                'deliver',
                lambda self, **kwargs: False,
            )

            submission.send_invite(to='failed_send@example.org', _from=user)
            key = get_user_rate_limit_key(user.pk)
            # Every attempt is counted toward the hourly limit, even failed ones
            assert cache.get(key, 0) == 1

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_hourly_rate_limit_blocks_and_sends_nothing_when_over_limit(self, event, submission, user):
        cache.clear()
        with scope(event=event):
            key = get_user_rate_limit_key(user.pk)
            cache.set(key, 20)

            # A send over the limit adds to the counter first, sees > 20, and sends nothing
            initial_count = SpeakerInvitation.objects.count()
            with pytest.raises(ValidationError) as exc:
                submission.send_invite(to='over@example.org', _from=user)
            assert 'maximum number of invitations for now' in str(exc.value)
            assert SpeakerInvitation.objects.count() == initial_count

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_record_speaker_invite_send_atomic_behavior(self, user):
        cache.clear()
        key = get_user_rate_limit_key(user.pk)
        cache.set(key, 18)

        # Counter is incremented first: 18 + 2 = 20 <= 20 -> allowed
        record_speaker_invite_send(user, amount=2)
        assert cache.get(key) == 20

        # Counter is incremented first: 20 + 1 = 21 > 20 -> rejected
        with pytest.raises(ValidationError, match='maximum number of invitations'):
            record_speaker_invite_send(user, amount=1)
        assert cache.get(key) == 21

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_organizer_rate_limit_exempt(self, event, submission, user):
        cache.clear()
        user.is_administrator = True
        user.save()

        # Fill cache to limit
        key = get_user_rate_limit_key(user.pk)
        cache.set(key, 50)

        # Admin is always permitted
        validate_speaker_invite_rate_limit(user)

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_rejected_addresses_strictly_rate_limited(self, event, submission, user, monkeypatch):
        cache.clear()
        with scope(event=event):
            # Simulate mail server rejecting every send
            def explode(*args, **kwargs):
                raise SendMailException('Mail server rejected address')

            monkeypatch.setattr('eventyay.common.mail.send_mail_now', explode)

            # A script targeting addresses the mail server rejects still consumes quota on every attempt
            for i in range(20):
                sub = Submission.objects.create(
                    event=event,
                    title=f'Rejected Talk {i}',
                    submission_type=submission.submission_type,
                )
                sub.speakers.add(user)
                sub.send_invite(to=f'rejected{i}@example.org', _from=user)

            # 21st attempt is strictly blocked by rate limit
            sub21 = Submission.objects.create(
                event=event,
                title='Rejected Talk 21',
                submission_type=submission.submission_type,
            )
            sub21.speakers.add(user)
            with pytest.raises(ValidationError) as exc:
                sub21.send_invite(to='rejected21@example.org', _from=user)
            assert 'maximum number of invitations for now' in str(exc.value)

    def test_atomic_acceptance_prevents_concurrent_overfill(self, event, submission, user, rf, monkeypatch):
        with scope(event=event):
            for i in range(9):
                extra_user = BaseUser.objects.create_user(email=f'seat{i}@example.org', password='password123')
                submission.speakers.add(extra_user)
            assert submission.co_speaker_count == 9

            user_a = BaseUser.objects.create_user(email='usera@example.org', password='password123')

            req = rf.post('/')
            req.user = user_a
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}

            # Simulate another request filling the 10th seat right before the atomic block runs
            orig_select_for_update = submission.__class__.all_objects.select_for_update

            def fake_select_for_update(*args, **kwargs):
                last_user = BaseUser.objects.create_user(email='concurrent_winner@example.org', password='password123')
                submission.speakers.add(last_user)
                return orig_select_for_update(*args, **kwargs)

            monkeypatch.setattr(submission.__class__.all_objects, 'select_for_update', fake_select_for_update)

            resp = view.post(req, code=submission.code, invitation=submission.invitation_token)
            assert resp.status_code == 302
            assert user_a not in submission.speakers.all()
            messages = list(get_messages(req))
            assert any('already reached the maximum of 10' in str(m) for m in messages)

    def test_concurrent_send_invite_race_for_last_slot(self, event, submission, user, monkeypatch):
        """Simulate two requests calling send_invite when 1 slot remains:
        Request A wins the lock, fills the 10th slot.
        Request B waits on the lock, wakes up, sees 10 slots filled, and raises ValidationError.
        """
        with scope(event=event):
            for i in range(9):
                extra_user = BaseUser.objects.create_user(email=f'seat{i}@example.org', password='password123')
                submission.speakers.add(extra_user)
            assert submission.co_speaker_count == 9

            orig_select_for_update = submission.__class__.all_objects.select_for_update

            # Simulate concurrent transaction filling the final slot right when Request B locks
            def concurrent_winner_interleaving(*args, **kwargs):
                winner = BaseUser.objects.create_user(email='race_winner@example.org', password='password123')
                submission.speakers.add(winner)
                return orig_select_for_update(*args, **kwargs)

            monkeypatch.setattr(submission.__class__.all_objects, 'select_for_update', concurrent_winner_interleaving)

            with pytest.raises(ValidationError) as exc:
                submission.send_invite(to='loser_candidate@example.org', _from=user)
            assert 'maximum of 10 co-speakers' in str(exc.value)
            assert not SpeakerInvitation.objects.filter(
                submission=submission, email='loser_candidate@example.org'
            ).exists()

    def test_concurrent_send_and_accept_interleaving(self, event, submission, user, rf, monkeypatch):
        """Simulate race between an invite acceptance and a send_invite when 1 slot remains."""
        with scope(event=event):
            for i in range(9):
                extra_user = BaseUser.objects.create_user(email=f'slot{i}@example.org', password='password123')
                submission.speakers.add(extra_user)
            assert submission.co_speaker_count == 9

            accepting_user = BaseUser.objects.create_user(email='accepting@example.org', password='password123')

            req = rf.post('/')
            req.user = accepting_user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}

            # Interleave: send_invite wins and takes the 10th slot right before accept lock executes
            orig_select_for_update = submission.__class__.all_objects.select_for_update

            def fake_select(*args, **kwargs):
                SpeakerInvitation.objects.create(
                    submission=submission,
                    email='concurrent_invitee@example.org',
                    invited_by=user,
                )
                return orig_select_for_update(*args, **kwargs)

            monkeypatch.setattr(submission.__class__.all_objects, 'select_for_update', fake_select)

            resp = view.post(req, code=submission.code, invitation=submission.invitation_token)
            assert resp.status_code == 302
            assert accepting_user not in submission.speakers.all()
            messages = list(get_messages(req))
            assert any('already reached the maximum of 10' in str(m) for m in messages)

    def test_email_crlf_header_injection_rejected(self, event, submission, user, rf):
        """Security: Ensure CRLF and email header injection payloads are rejected by form and view."""
        with scope(event=event):
            injection_payloads = [
                'victim@example.org\r\nBcc: evil@example.org',
                'victim@example.org\nCC: attacker@example.org',
                'victim@example.org\rSubject: Spam',
                'victim@example.org%0Aevil@example.org',
                'attacker@example.org\r\n\r\nEvil Body',
            ]
            for payload in injection_payloads:
                form = SubmissionInvitationForm(
                    submission=submission,
                    speaker=user,
                    data={'speaker': payload},
                )
                assert not form.is_valid(), f"Payload '{payload}' was improperly accepted"
                assert 'speaker' in form.errors

            req = rf.get('/', {'email': 'test@example.org\r\nBcc: evil@example.org'})
            req.user = user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteView()
            view.request = req
            view.kwargs = {'code': submission.code}
            view.get(req, code=submission.code)
            messages = list(get_messages(req))
            assert any(str(phrases.cfp.invite_invalid_email) in str(m) for m in messages)

    def test_multi_tenant_isolation_cross_event_access_blocked(self, event, submission, user, rf):
        """Security: An invitation token from Event A cannot be accessed or accepted in Event B."""
        with scope(event=event):
            assert submission.event == event
            code = submission.code
            token = submission.invitation_token

        other_organizer = Organizer.objects.create(name='Other Org', slug='otherorg')
        other_event = Event.objects.create(
            organizer=other_organizer,
            name='Other Event',
            slug='otherevent',
            date_from=event.date_from,
            date_to=event.date_to,
        )

        user_b = BaseUser.objects.create_user(email='user_b@example.org', password='password123')

        req = rf.post('/')
        req.user = user_b
        req.event = other_event
        req.session = SessionStore()
        req._messages = FallbackStorage(req)
        req.LANGUAGE_CODE = 'en'

        view = SubmissionInviteAcceptView()
        view.request = req
        view.kwargs = {'code': code, 'invitation': token}

        with scope(event=other_event):
            resp = view.dispatch(req, code=code, invitation=token)
            assert resp.status_code == 302
            assert str(other_event.slug) in resp.url
            messages = list(get_messages(req))
            assert any('invitation link is invalid' in str(m).lower() for m in messages)
            assert user_b not in submission.speakers.all()

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_cache_failure_fails_closed_on_send_and_resend(self, event, submission, user, monkeypatch):
        """Security: Fail-closed defense ensures rate limit bypass is impossible during cache outages."""
        cache.clear()
        with scope(event=event):
            def broken_cache_op(*args, **kwargs):
                raise Exception('Redis connection refused')

            monkeypatch.setattr(cache, 'add', broken_cache_op)
            monkeypatch.setattr(cache, 'incr', broken_cache_op)

            with pytest.raises(ValidationError, match='cannot be sent right now'):
                record_speaker_invite_send(user, amount=1)

            with pytest.raises(ValidationError, match='cannot be sent right now'):
                submission.send_invite(to='outage_test@example.org', _from=user)

            invitation = SpeakerInvitation.objects.create(
                submission=submission,
                email='resend_outage@example.org',
                invited_by=user,
            )
            assert invitation.resend(requestor=user, orga=False) is False

    def test_cfp_wizard_profile_step_successful_co_speaker_invite(self, event, user, rf):
        """End-to-End: CfP submission wizard successfully creates and delivers co-speaker invite."""
        djmail.outbox = []
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name='Talk')
            sub = Submission.objects.create(
                title='E2E Wizard Proposal',
                event=event,
                submission_type=sub_type,
            )
            sub.speakers.add(user)

            req = rf.post('/')
            req.user = user
            req.event = event
            req.submission = sub
            req.session = SessionStore()
            req._messages = FallbackStorage(req)

            step = ProfileStep(event=event)
            step.cfp_session = {'data': {}}
            form_mock = type('FormMock', (), {
                'cleaned_data': {'additional_speaker': 'wizard_partner@example.org'},
                'user': None,
                'save': lambda *args, **kwargs: None,
                'is_valid': lambda *args, **kwargs: True,
            })()
            step.get_form = lambda from_storage=True: form_mock

            step.done(req, draft=False)
            invites = SpeakerInvitation.objects.filter(submission=sub, email='wizard_partner@example.org')
            assert invites.exists()
            assert invites.first().status == SpeakerInvitationStates.PENDING
            assert len(djmail.outbox) == 1
            assert djmail.outbox[0].to == ['wizard_partner@example.org']

    def test_cfp_wizard_profile_step_draft_suppresses_invites(self, event, user, rf):
        """End-to-End: Saving a draft proposal in CfP wizard suppresses sending co-speaker invites."""
        djmail.outbox = []
        with scope(event=event):
            sub_type = SubmissionType.objects.create(event=event, name='Talk')
            sub = Submission.objects.create(
                title='Draft Proposal',
                event=event,
                submission_type=sub_type,
            )
            sub.speakers.add(user)

            req = rf.post('/')
            req.user = user
            req.event = event
            req.submission = sub
            req.session = SessionStore()
            req._messages = FallbackStorage(req)

            step = ProfileStep(event=event)
            step.cfp_session = {'data': {}}
            form_mock = type('FormMock', (), {
                'cleaned_data': {'additional_speaker': 'draft_partner@example.org'},
                'user': None,
                'save': lambda *args, **kwargs: None,
                'is_valid': lambda *args, **kwargs: True,
            })()
            step.get_form = lambda from_storage=True: form_mock

            step.done(req, draft=True)
            assert not SpeakerInvitation.objects.filter(submission=sub).exists()
            assert len(djmail.outbox) == 0

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_end_to_end_invite_resend_revoke_reinvite_lifecycle(self, event, submission, user, rf):
        """End-to-End: Complete lifecycle of an invite through send, resend x3, limit, revoke, re-invite, accept."""
        cache.clear()
        djmail.outbox = []
        with scope(event=event):
            invitation = submission.send_invite(to='lifecycle@example.org', _from=user)
            assert invitation.resend_count == 0
            assert submission.co_speaker_count == 1
            assert len(djmail.outbox) == 1

            for i in range(3):
                assert invitation.resend(requestor=user, orga=False) is True
                assert invitation.resend_count == i + 1

            with pytest.raises(ValidationError, match='maximum of 3 times'):
                invitation.resend(requestor=user, orga=False)

            assert invitation.revoke(person=user, orga=False) is True
            assert not SpeakerInvitation.objects.filter(pk=invitation.pk).exists()
            assert submission.co_speaker_count == 0

            new_invitation = submission.send_invite(to='lifecycle@example.org', _from=user)
            assert new_invitation.pk != invitation.pk
            # Re-inviting the same address does not reset the resend count
            assert new_invitation.resend_count == 3
            assert not new_invitation.can_resend
            assert new_invitation.status == SpeakerInvitationStates.PENDING

            partner = BaseUser.objects.create_user(email='lifecycle@example.org', password='password123')
            req = rf.post('/')
            req.user = partner
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            resp = view.post(req, code=submission.code, invitation=submission.invitation_token)
            assert resp.status_code == 302

            new_invitation.refresh_from_db()
            assert new_invitation.status == SpeakerInvitationStates.ACCEPTED
            assert partner in submission.speakers.all()
            assert submission.confirmed_co_speakers_count == 1

    def test_resend_without_mail_returns_false_defensively(self, event, submission, user):
        """Defensive: resend() returns False gracefully if mail object is None."""
        with scope(event=event):
            invitation = SpeakerInvitation.objects.create(
                submission=submission,
                email='nomail@example.org',
                invited_by=user,
            )
            assert invitation.mail is None
            assert invitation.resend(requestor=user, orga=False) is False
            assert invitation.resend(requestor=user, orga=True) is False

    def test_accept_invitation_matches_by_user_fk(self, event, submission, user, rf):
        """Ensure an invitation with user FK is accepted even if user email has different casing or alias."""
        with scope(event=event):
            target_user = BaseUser.objects.create_user(email='UserAlias@example.org', password='password123')
            invitation = SpeakerInvitation.objects.create(
                submission=submission,
                email='useralias@example.org',
                user=target_user,
                invited_by=user,
            )

            req = rf.post('/')
            req.user = target_user
            req.event = event
            req.session = SessionStore()
            req._messages = FallbackStorage(req)
            req.LANGUAGE_CODE = 'en'

            view = SubmissionInviteAcceptView()
            view.request = req
            view.kwargs = {'code': submission.code, 'invitation': submission.invitation_token}
            resp = view.post(req, code=submission.code, invitation=submission.invitation_token)
            assert resp.status_code == 302

            invitation.refresh_from_db()
            assert invitation.status == SpeakerInvitationStates.ACCEPTED
            assert target_user in submission.speakers.all()

    def test_pending_invitations_count_case_insensitive_against_speaker_emails(self, event, submission, user):
        """Ensure pending_invitations_count excludes speakers whose email has mixed casing."""
        with scope(event=event):
            cased_speaker = BaseUser.objects.create_user(email='UpperCase@Example.Org', password='password123')
            submission.speakers.add(cased_speaker)

            # Create an invitation for the lowercased version of the same speaker
            SpeakerInvitation.objects.create(
                submission=submission,
                email='uppercase@example.org',
                invited_by=user,
            )

            # Should be excluded from pending count because the speaker is already confirmed
            assert submission.pending_invitations_count == 0
            assert submission.confirmed_co_speakers_count == 1
            assert submission.co_speaker_count == 1

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_resend_race_condition_protection(self, event, submission, user):
        """Simulate concurrent parallel resends incrementing past MAX_RESENDS."""
        with scope(event=event):
            invitation = submission.send_invite('target@example.org', _from=user)
            assert invitation.resend_count == 0

            # A parallel request already used up the resends after our read
            cache.set(get_invitation_resend_key(invitation), 3)
            with mock.patch(
                'eventyay.base.models.speaker_invitation.get_invitation_resend_count',
                return_value=0,
            ):
                with pytest.raises(ValidationError, match='maximum of 3 times'):
                    invitation.resend(requestor=user, orga=False)

    def test_cache_failure_fails_closed(self, user):
        """Ensure the rate limit check fails closed if the cache throws an exception."""
        with mock.patch('eventyay.base.services.speaker_invite_limits.cache.get', side_effect=Exception('Redis down')):
            with pytest.raises(ValidationError, match='cannot be sent right now'):
                validate_speaker_invite_rate_limit(user)

    def test_edit_view_pending_invitations_excludes_speaker_email_without_user_fk(self, event, submission, user):
        """Ensure SubmissionsEditView.pending_invitations excludes invitations by email even without user FK."""
        from eventyay.cfp.views.user import SubmissionsEditView

        with scope(event=event):
            other_speaker = BaseUser.objects.create_user(email='OtherSpeaker@Example.Org', password='password123')
            submission.speakers.add(other_speaker)

            # Invitation without user FK
            invitation = SpeakerInvitation.objects.create(
                submission=submission,
                email='otherspeaker@example.org',
                invited_by=user,
            )

            view = SubmissionsEditView()
            view.object = submission
            pending = list(view.pending_invitations)
            assert invitation not in pending


