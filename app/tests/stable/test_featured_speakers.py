from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse
from django_scopes import scope

from eventyay.base.models import SpeakerProfile
from eventyay.talk_rules.agenda import is_pre_agenda_featured_public, is_speaker_viewable

User = get_user_model()


def _event_base_path(event):
    return urlparse(str(event.urls.base)).path.rstrip('/')


def _assert_speakers_list_redirects(client, event, *, expected_message):
    speakers_list_url = reverse(
        'agenda:speakers',
        kwargs={
            'event': event.slug,
            'organizer': event.organizer.slug,
        },
    )
    response = client.get(speakers_list_url, follow=True)
    assert response.status_code == 200
    assert response.request['PATH_INFO'].rstrip('/') == _event_base_path(event)
    messages = [str(message) for message in get_messages(response.wsgi_request)]
    assert expected_message in messages


@pytest.mark.django_db
def test_featured_speaker_without_talks_still_viewable_after_schedule_release(client, event):
    """Featured speakers with no sessions stay public after the schedule is released."""
    with scope(event=event):
        user = User.objects.create_user(
            email='featured-only@example.com',
            password='testpass123',
            fullname='Featured Only Speaker',
        )
        profile = SpeakerProfile.objects.create(
            event=event,
            user=user,
            biography='Featured biography.',
            is_featured=True,
        )
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.talks_published = False
        event.save(update_fields=['feature_flags', 'talks_published'])
        event.release_schedule('v1')
        event.talks_published = True
        event.save(update_fields=['talks_published'])

    with scope(event=event):
        assert is_pre_agenda_featured_public(None, event) is False
        assert is_speaker_viewable(None, profile) is True

    speaker_url = reverse(
        'agenda:speaker',
        kwargs={
            'code': user.code,
            'event': event.slug,
            'organizer': event.organizer.slug,
        },
    )
    response = client.get(speaker_url, follow=True)
    assert response.status_code == 200
    assert user.fullname in response.content.decode()
    assert '"exports_disabled": true' in response.context['schedule_json']


@pytest.mark.django_db
def test_featured_speakers_list_blocked_before_public_schedule_release(client, event):
    """Featured speakers stay on the info page, but the full list stays hidden until release."""
    with scope(event=event):
        user = User.objects.create_user(
            email='featured-pre-release@example.com',
            password='testpass123',
            fullname='Pre Release Featured Speaker',
        )
        SpeakerProfile.objects.create(
            event=event,
            user=user,
            biography='Featured biography.',
            is_featured=True,
        )
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.talks_published = False
        event.save(update_fields=['feature_flags', 'talks_published'])
        event.release_schedule('v1')

    landing = client.get(event.urls.base)
    assert landing.status_code == 200
    widget_schedule = landing.context['featured_speakers_widget_schedule']
    assert widget_schedule is not None
    assert widget_schedule['speakers_list_public'] is False
    assert '"speakers_list_public": false' in landing.context['featured_speakers_widget_schedule_json']
    assert 'speakers-list-public="false"' in landing.text
    assert landing.context['featured_speakers_list_public'] is False

    speaker_url = reverse(
        'agenda:speaker',
        kwargs={
            'code': user.code,
            'event': event.slug,
            'organizer': event.organizer.slug,
        },
    )
    assert client.get(speaker_url, follow=True).status_code == 200

    _assert_speakers_list_redirects(client, event, expected_message='No published schedule.')


@pytest.mark.django_db
def test_speakers_list_blocked_when_no_schedule_released(client, event):
    """Speakers list redirects to the info page when no schedule version has been released."""
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])
        assert event.current_schedule is None

    _assert_speakers_list_redirects(client, event, expected_message='No published schedule.')


@pytest.mark.django_db
def test_speakers_list_blocked_when_featured_visible_without_schedule(client, event):
    """Speakers list redirects when only featured sessions are public without a released schedule."""
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.feature_flags['show_featured'] = 'always'
        event.save(update_fields=['talks_published', 'feature_flags'])
        assert event.current_schedule is None

    _assert_speakers_list_redirects(client, event, expected_message='No published schedule.')


@pytest.mark.django_db
def test_speakers_list_blocked_for_organiser_until_public_release(organizer_client, event):
    """Organisers use orga/WIP preview; the public speakers page redirects until release."""
    with scope(event=event):
        user = User.objects.create_user(
            email='featured-orga-pre-release@example.com',
            password='testpass123',
            fullname='Organiser Pre Release Speaker',
        )
        SpeakerProfile.objects.create(
            event=event,
            user=user,
            biography='Featured biography.',
            is_featured=True,
        )
        event.talks_published = True
        event.private_testmode = True
        event.settings.private_testmode_talks = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'private_testmode', 'feature_flags'])
        event.release_schedule('v1')

    _assert_speakers_list_redirects(
        organizer_client,
        event,
        expected_message='No published schedule.',
    )


@pytest.mark.django_db
def test_speakers_list_blocked_in_private_talk_testmode(client, event):
    """Speakers list stays private while talk pages are in private test mode."""
    with scope(event=event):
        user = User.objects.create_user(
            email='featured-private@example.com',
            password='testpass123',
            fullname='Featured Private Speaker',
        )
        SpeakerProfile.objects.create(
            event=event,
            user=user,
            biography='Featured biography.',
            is_featured=True,
        )
        event.talks_published = True
        event.private_testmode = True
        event.settings.private_testmode_talks = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'private_testmode', 'feature_flags'])
        event.release_schedule('v1')

    landing = client.get(event.urls.base)
    assert landing.status_code == 200
    assert landing.context['featured_speakers_list_public'] is False

    _assert_speakers_list_redirects(client, event, expected_message='No published schedule.')
