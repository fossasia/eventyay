import datetime as dt
from urllib.parse import unquote_plus

import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.base.models import Room, Submission, SubmissionType, TalkSlot


@pytest.fixture
def speaker_with_sessions(event, user):
    with scope(event=event):
        event.talks_published = True
        event.settings.set('show_schedule', True)
        event.save()
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        room = Room.objects.create(event=event, name='Room A')

        sub1 = Submission.objects.create(
            title='Docker Up, PR Out',
            event=event,
            submission_type=submission_type,
            content_locale='en',
            abstract='Learn to set up Eventyay',
        )
        sub1.speakers.add(user)
        sub1.accept()
        sub1.confirm()

        sub2 = Submission.objects.create(
            title='Can You Get It Merged',
            event=event,
            submission_type=submission_type,
            content_locale='en',
            abstract='Code review best practices',
        )
        sub2.speakers.add(user)
        sub2.accept()
        sub2.confirm()

        slot1 = {
            'is_visible': True,
            'start': event.date_from + dt.timedelta(hours=10),
            'end': event.date_from + dt.timedelta(hours=11),
            'room': room,
        }
        slot2 = {
            'is_visible': True,
            'start': event.date_from + dt.timedelta(hours=14),
            'end': event.date_from + dt.timedelta(hours=15),
            'room': room,
        }
        TalkSlot.objects.update_or_create(submission=sub1, schedule=event.wip_schedule, defaults=slot1)
        TalkSlot.objects.update_or_create(submission=sub2, schedule=event.wip_schedule, defaults=slot2)
        event.release_schedule('v1')
        TalkSlot.objects.update_or_create(submission=sub1, schedule=event.current_schedule, defaults=slot1)
        TalkSlot.objects.update_or_create(submission=sub2, schedule=event.current_schedule, defaults=slot2)
        profile = user.event_profile(event)
        return profile, sub1, sub2, room


@pytest.mark.django_db
def test_speaker_google_calendar_redirect_multiple_sessions(speaker_with_sessions, client, event):
    profile, sub1, sub2, _ = speaker_with_sessions
    url = reverse(
        'agenda:speaker.talks.google-calendar',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )
    response = client.get(url, follow=False)
    assert response.status_code == 302
    assert 'calendar.google.com/calendar/r?' in response['Location']
    assert 'cid=' in response['Location']
    loc = unquote_plus(response['Location'])
    assert 'cid=http://' in loc
    assert 'talks.ics' in loc


@pytest.mark.django_db
def test_speaker_google_calendar_redirect_https_replaces_to_http(speaker_with_sessions, client, event, settings):
    settings.SITE_URL = 'https://eventyay.example.com'
    profile, _, _, _ = speaker_with_sessions
    url = reverse(
        'agenda:speaker.talks.google-calendar',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )
    response = client.get(url, follow=False)
    assert response.status_code == 302
    loc = unquote_plus(response['Location'])
    assert 'cid=http://eventyay.example.com' in loc
    assert 'https://eventyay.example.com' not in loc


@pytest.mark.django_db
def test_speaker_google_calendar_redirect_specific_session(speaker_with_sessions, client, event):
    profile, sub1, sub2, room = speaker_with_sessions
    base_url = reverse(
        'agenda:speaker.talks.google-calendar',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )

    # Session 1
    resp1 = client.get(f'{base_url}?talk={sub1.code}', follow=False)
    assert resp1.status_code == 302
    loc1 = unquote_plus(resp1['Location'])
    assert 'calendar.google.com/calendar/render?action=TEMPLATE' in loc1
    assert sub1.title in loc1
    assert room.name in loc1

    # Session 2
    resp2 = client.get(f'{base_url}?talk={sub2.code}', follow=False)
    assert resp2.status_code == 302
    loc2 = unquote_plus(resp2['Location'])
    assert 'calendar.google.com/calendar/render?action=TEMPLATE' in loc2
    assert sub2.title in loc2
    assert room.name in loc2

    # Non-existent session
    resp_invalid = client.get(f'{base_url}?talk=NONEXISTENT', follow=False)
    assert resp_invalid.status_code == 404


@pytest.mark.django_db
def test_speaker_google_calendar_redirect_single_session(event, user, client):
    with scope(event=event):
        event.talks_published = True
        event.settings.set('show_schedule', True)
        event.save()
        submission_type = SubmissionType.objects.create(event=event, name='Talk')
        room = Room.objects.create(event=event, name='Solo Hall')

        sub = Submission.objects.create(
            title='Solo Session',
            event=event,
            submission_type=submission_type,
            content_locale='en',
            abstract='Solo abstract',
        )
        sub.speakers.add(user)
        sub.accept()
        sub.confirm()

        slot = {
            'is_visible': True,
            'start': event.date_from + dt.timedelta(hours=10),
            'end': event.date_from + dt.timedelta(hours=11),
            'room': room,
        }
        TalkSlot.objects.update_or_create(submission=sub, schedule=event.wip_schedule, defaults=slot)
        event.release_schedule('v1')
        TalkSlot.objects.update_or_create(submission=sub, schedule=event.current_schedule, defaults=slot)
        profile = user.event_profile(event)

    url = reverse(
        'agenda:speaker.talks.google-calendar',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )
    response = client.get(url, follow=False)
    assert response.status_code == 302
    loc = unquote_plus(response['Location'])
    assert 'calendar.google.com/calendar/render?action=TEMPLATE' in loc
    assert sub.title in loc
    assert room.name in loc


@pytest.mark.django_db
def test_speaker_webcal_redirect(speaker_with_sessions, client, event):
    profile, _, _, _ = speaker_with_sessions
    url = reverse(
        'agenda:speaker.talks.webcal',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )
    response = client.get(url, follow=False)
    assert response.status_code == 302
    assert response['Location'].startswith('webcal://')
    assert 'talks.ics' in response['Location']


@pytest.mark.django_db
def test_speaker_export_feed_handles_roomless_session(speaker_with_sessions, client, event):
    profile, sub1, sub2, _ = speaker_with_sessions
    with scope(event=event):
        slot2 = TalkSlot.objects.get(submission=sub2, schedule=event.current_schedule)
        slot2.room = None
        slot2.save()

    url = reverse(
        'agenda:speaker.talks.google-calendar',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )
    response = client.get(url, follow=False)
    assert response.status_code == 302
    assert 'cid=' in response['Location']

    ical_url = reverse(
        'agenda:speaker.talks.ical',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )
    ical_response = client.get(ical_url)
    assert ical_response.status_code == 200
    content = ical_response.content.decode()
    # RFC 5545 escapes commas in TEXT values as '\,'
    assert 'Docker Up' in content
    assert sub2.title in content


@pytest.mark.django_db
def test_speaker_export_feed_respects_public_abstract_false(speaker_with_sessions, client, event):
    profile, sub1, sub2, _ = speaker_with_sessions
    with scope(event=event):
        cfp = event.cfp
        fields = dict(cfp.fields)
        fields['abstract'] = {**fields.get('abstract', {}), 'public': False}
        cfp.fields = fields
        cfp.save()

    ical_url = reverse(
        'agenda:speaker.talks.ical',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug, 'code': profile.user.code},
    )
    ical_response = client.get(ical_url)
    assert ical_response.status_code == 200
    content = ical_response.content.decode()
    assert sub1.abstract not in content
    assert sub2.abstract not in content
