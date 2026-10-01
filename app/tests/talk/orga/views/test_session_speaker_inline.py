import pytest
from django.test import Client
from django_scopes import scope

from eventyay.base.models import Submission, User
from eventyay.base.models.mail import MailTemplateRoles


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('ajax', [False, True])
@pytest.mark.parametrize('existing', [False, True])
def test_add_speaker_stays_on_session_and_invites(orga_client, event, submission, other_speaker, ajax, existing):
    email = other_speaker.email if existing else 'inline-speaker@example.test'
    name = other_speaker.fullname if existing else 'Inline Speaker'
    headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
    with scope(event=event):
        original_speakers = set(submission.speakers.values_list('pk', flat=True))
        response = orga_client.post(
            submission.orga_urls.speakers,
            {'email': email, 'name': name, 'biography': 'Speaker biography'},
            **headers,
        )
        speaker = User.objects.get(email=email)
        assert set(submission.speakers.values_list('pk', flat=True)) == original_speakers | {speaker.pk}
        role = MailTemplateRoles.EXISTING_SPEAKER_INVITE if existing else MailTemplateRoles.NEW_SPEAKER_INVITE
        assert speaker.mails.filter(event=event, template=event.get_mail_template(role)).exists()
        if ajax:
            assert response.status_code == 200
            assert 'Location' not in response
            data = response.json()
            assert data['speaker_code'] == speaker.code
            assert f'id="session-speaker-{speaker.code}"' in data['speakers']
            assert name in data['speakers']
            assert name in data['speaker_names']
            assert '<html' not in data['speakers']
            assert data['message']
        else:
            assert response.status_code == 302
            assert response.url == submission.orga_urls.speakers
            page = orga_client.get(response.url)
            assert f'id="session-speaker-{speaker.code}"' in page.text


@pytest.mark.parametrize(
    'data',
    [
        {'email': 'invalid-email', 'name': 'Speaker'},
        {'email': 'missing-name@example.test'},
    ],
)
def test_invalid_inline_speaker_returns_errors_without_changes(orga_client, event, submission, data):
    with scope(event=event):
        original_speakers = set(submission.speakers.values_list('pk', flat=True))
        mail_count = event.queued_mails.count()
        response = orga_client.post(
            submission.orga_urls.speakers,
            data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert response.status_code == 400
        assert response.json()['errors']
        assert set(submission.speakers.values_list('pk', flat=True)) == original_speakers
        assert event.queued_mails.count() == mail_count


def test_inline_speaker_renders_required_biography(orga_client, event, submission):
    with scope(event=event):
        event.cfp.fields['biography']['visibility'] = 'required'
        event.cfp.save()
        page = orga_client.get(submission.orga_urls.speakers)
        assert 'name="biography"' in page.text
        response = orga_client.post(
            submission.orga_urls.speakers,
            {'email': 'needs-bio@example.test', 'name': 'Needs biography'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert response.status_code == 400
        assert any(error['label'] == 'Biography' for error in response.json()['errors'])
        assert not User.objects.filter(email='needs-bio@example.test').exists()


def test_reviewer_cannot_post_inline_speaker(review_client, event, submission):
    with scope(event=event):
        count = submission.speakers.count()
        response = review_client.post(
            submission.orga_urls.speakers,
            {'email': 'unauthorized@example.test', 'name': 'Unauthorized'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert response.status_code == 404
        assert submission.speakers.count() == count
        assert not User.objects.filter(email='unauthorized@example.test').exists()


def test_inline_speaker_rejects_another_events_session(orga_client, event, other_event, submission):
    with scope(event=other_event):
        foreign = Submission.objects.create(
            event=other_event,
            title='Foreign session',
            submission_type=other_event.cfp.default_type,
        )
    with scope(event=event):
        response = orga_client.post(
            str(submission.orga_urls.speakers).replace(submission.code, foreign.code),
            {'email': 'foreign-session@example.test', 'name': 'Foreign'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert response.status_code == 404
        assert not User.objects.filter(email='foreign-session@example.test').exists()


def test_inline_speaker_requires_csrf(orga_user, event, submission):
    client = Client(enforce_csrf_checks=True)
    client.force_login(orga_user)
    with scope(event=event):
        response = client.post(
            submission.orga_urls.speakers,
            {'email': 'csrf@example.test', 'name': 'CSRF'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        assert response.status_code == 403
        assert not User.objects.filter(email='csrf@example.test').exists()
