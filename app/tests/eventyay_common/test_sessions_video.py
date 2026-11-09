import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.base.models import Submission, SubmissionType
from eventyay.eventyay_common.templatetags.session_tags import can_review_video, speaker_review_url


@pytest.fixture
def confirmed_submission(db, event, user):
    with scope(event=event):
        event.plugins = 'veditor'
        event.save()
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        sub = Submission.objects.create(
            title='Confirmed Video Talk',
            event=event,
            submission_type=submission_type,
            state='confirmed',
            abstract='Talk abstract',
            content_locale='en',
        )
        sub.speakers.add(user)
        return sub


@pytest.mark.django_db
def test_confirmed_session_shows_video_review_button(authenticated_client, event, confirmed_submission):
    response = authenticated_client.get(reverse('eventyay_common:sessions'))
    assert response.status_code == 200
    content = response.content.decode()

    assert 'Confirmed Video Talk' in content
    assert 'Review Video in VEditor' in content
    assert 'fa-video-camera' in content

    expected_url = reverse(
        'plugins:veditor:speaker-review',
        kwargs={
            'organizer': event.organizer.slug,
            'event': event.slug,
            'talk_code': confirmed_submission.code,
        },
    )
    assert expected_url in content


@pytest.mark.django_db
def test_unconfirmed_session_hides_video_review_button(authenticated_client, event, user):
    with scope(event=event):
        event.plugins = 'veditor'
        event.save()
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        sub = Submission.objects.create(
            title='Accepted But Not Confirmed Talk',
            event=event,
            submission_type=submission_type,
            state='accepted',
            abstract='Talk abstract',
            content_locale='en',
        )
        sub.speakers.add(user)

    response = authenticated_client.get(reverse('eventyay_common:sessions'))
    assert response.status_code == 200
    content = response.content.decode()

    assert 'Accepted But Not Confirmed Talk' in content
    assert 'Review Video in VEditor' not in content
    assert 'fa-video-camera' not in content


@pytest.mark.django_db
def test_session_without_veditor_plugin_hides_video_review_button(authenticated_client, event, user):
    with scope(event=event):
        event.plugins = ''
        event.save()
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        sub = Submission.objects.create(
            title='Talk In Event Without VEditor',
            event=event,
            submission_type=submission_type,
            state='confirmed',
            abstract='Talk abstract',
            content_locale='en',
        )
        sub.speakers.add(user)

    response = authenticated_client.get(reverse('eventyay_common:sessions'))
    assert response.status_code == 200
    content = response.content.decode()

    assert 'Talk In Event Without VEditor' in content
    assert 'Review Video in VEditor' not in content
    assert 'fa-video-camera' not in content


@pytest.mark.django_db
def test_table_header_includes_video_column(authenticated_client, event, confirmed_submission):
    response = authenticated_client.get(reverse('eventyay_common:sessions'))
    assert response.status_code == 200
    content = response.content.decode()

    assert '<th>Video</th>' in content


def test_session_tags_edge_cases():
    assert can_review_video(None) is False
    assert speaker_review_url(None) == ''
