import pytest
from django_scopes import scope

from eventyay.base.models import SpeakerProfile, Submission, SubmissionStates, User
from eventyay.orga.forms.relationships import SessionSpeakersForm, SpeakerSessionAssignmentForm


pytestmark = pytest.mark.django_db


@pytest.fixture
def speaker_edit_data(speaker):
    return {'fullname': speaker.fullname, 'email': speaker.email, 'biography': 'Speaker biography'}


@pytest.fixture
def session_edit_data(submission):
    return {
        'title': submission.title,
        'abstract': submission.abstract,
        'submission_type': submission.submission_type_id,
        'content_locale': 'en',
        'slot_count': 1,
        'resource-TOTAL_FORMS': 0,
        'resource-INITIAL_FORMS': 0,
        'speakers-present': '1',
    }


def test_existing_speaker_can_link_session(orga_client, event, speaker, other_submission, speaker_edit_data):
    with scope(event=event):
        profile = speaker.event_profile(event)
        speaker_edit_data.update(link_existing_session='on', existing_session_id=other_submission.pk)
        response = orga_client.post(profile.orga_urls.base, speaker_edit_data)
        assert response.status_code == 302
        assert other_submission.speakers.filter(pk=speaker.pk).exists()
        assert other_submission.speakers.count() == 2
        assert speaker.submissions.filter(pk=other_submission.pk).exists()


def test_existing_speaker_can_create_session(orga_client, event, speaker, speaker_edit_data):
    with scope(event=event):
        speaker_edit_data.update(
            {
                'add_session': 'on',
                'session-title': 'New session for existing speaker',
                'session-abstract': 'Session abstract',
                'session-submission_type': event.cfp.default_type.pk,
                'session-content_locale': 'en',
                'session-state': SubmissionStates.SUBMITTED,
            }
        )
        response = orga_client.post(speaker.event_profile(event).orga_urls.base, speaker_edit_data)
        assert response.status_code == 302
        session = event.submissions.get(title='New session for existing speaker')
        assert list(session.speakers.all()) == [speaker]


def test_invalid_new_session_does_not_save_speaker(orga_client, event, speaker, speaker_edit_data):
    with scope(event=event):
        speaker_edit_data.update(fullname='Unsaved change', add_session='on')
        response = orga_client.post(speaker.event_profile(event).orga_urls.base, speaker_edit_data)
        assert response.status_code == 200
        speaker.refresh_from_db()
        assert speaker.fullname != 'Unsaved change'
        assert not event.submissions.exists()


@pytest.mark.parametrize('state', [SubmissionStates.SUBMITTED, SubmissionStates.DRAFT, SubmissionStates.DELETED])
def test_speaker_assignment_rejects_other_event_and_hidden_sessions(event, other_event, orga_user, state):
    with scope(event=other_event):
        foreign = Submission.objects.create(
            event=other_event, title='Foreign session', state=state, submission_type=other_event.cfp.default_type
        )
    with scope(event=event):
        form = SpeakerSessionAssignmentForm(
            {'link_existing_session': 'on', 'existing_session_id': foreign.pk}, event=event, user=orga_user
        )
        assert not form.is_valid()
        assert 'existing_session_id' in form.errors
        hidden = Submission.objects.create(
            event=event, title='Local session', state=state, submission_type=event.cfp.default_type
        )
        if state != SubmissionStates.SUBMITTED:
            form = SpeakerSessionAssignmentForm(
                {'link_existing_session': 'on', 'existing_session_id': hidden.pk}, event=event, user=orga_user
            )
            assert not form.is_valid()


def test_reviewer_cannot_assign_sessions(event, review_user, submission):
    with scope(event=event):
        for data in ({'add_session': 'on'}, {'link_existing_session': 'on', 'existing_session_id': submission.pk}):
            form = SpeakerSessionAssignmentForm(data, event=event, user=review_user)
            assert not form.is_valid()


def test_session_edit_can_replace_existing_speakers(orga_client, event, submission, other_speaker, session_edit_data):
    with scope(event=event):
        session_edit_data['speakers'] = [other_speaker.pk]
        response = orga_client.post(submission.orga_urls.edit, session_edit_data)
        assert response.status_code == 302
        assert list(submission.speakers.all()) == [other_speaker]
        assert other_speaker.submissions.filter(pk=submission.pk).exists()


def test_session_edit_can_remove_all_speakers(orga_client, event, submission, session_edit_data):
    with scope(event=event):
        response = orga_client.post(submission.orga_urls.edit, session_edit_data)
        assert response.status_code == 302
        assert not submission.speakers.exists()


def test_session_edit_without_speaker_fields_preserves_links(orga_client, event, submission, session_edit_data):
    session_edit_data.pop('speakers-present')
    with scope(event=event):
        response = orga_client.post(submission.orga_urls.edit, session_edit_data)
        assert response.status_code == 302
        assert submission.speakers.count() == 1


def test_session_edit_can_invite_new_speaker(orga_client, event, submission, speaker, session_edit_data):
    session_edit_data.update(
        {
            'speakers': [speaker.pk],
            'speaker-email': 'new-speaker@example.org',
            'speaker-name': 'New speaker',
            'speaker-biography': 'New speaker biography',
        }
    )
    with scope(event=event):
        response = orga_client.post(submission.orga_urls.edit, session_edit_data)
        assert response.status_code == 302
        new_speaker = User.objects.get(email='new-speaker@example.org')
        assert submission.speakers.filter(pk=new_speaker.pk).exists()
        assert SpeakerProfile.objects.filter(event=event, user=new_speaker).exists()
        assert new_speaker.mails.filter(event=event).exists()


def test_invalid_invitation_does_not_change_links(orga_client, event, submission, speaker, session_edit_data):
    session_edit_data.update({'speaker-email': 'not-an-email', 'title': 'Unsaved title'})
    with scope(event=event):
        response = orga_client.post(submission.orga_urls.edit, session_edit_data)
        assert response.status_code == 200
        submission.refresh_from_db()
        assert submission.title != 'Unsaved title'
        assert list(submission.speakers.all()) == [speaker]


def test_session_speaker_choices_are_event_scoped(event, other_event, submission):
    foreign = User.objects.create_user(email='foreign@example.org', fullname='Foreign speaker')
    with scope(event=other_event):
        SpeakerProfile.objects.create(event=other_event, user=foreign)
    with scope(event=event):
        form = SessionSpeakersForm({'speakers': [foreign.pk]}, event=event, submission=submission)
        assert not form.is_valid()
        assert 'speakers' in form.errors


def test_edit_pages_show_relationship_controls(orga_client, event, speaker, submission):
    with scope(event=event):
        response = orga_client.get(speaker.event_profile(event).orga_urls.base)
        assert 'Create a new session for this speaker' in response.text
        assert 'Link an existing session instead' in response.text
        response = orga_client.get(submission.orga_urls.edit)
        assert 'name="speakers"' in response.text
        assert 'Add/invite a new speaker' in response.text
