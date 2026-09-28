import json

import pytest
from django.core.cache import cache
from django_scopes import scope

from eventyay.base.models import SubmissionFavourite


def _publish_user(user):
    user.code = 'STARUSER'
    user.show_publicly = True
    user.fullname = 'Star User'
    user.save(update_fields=['code', 'show_publicly', 'fullname'])


def _stars_url(event, code='STARUSER'):
    return f'{event.urls.base}people/{code}/stars/'


def _publish_talk_pages(event):
    event.talks_published = True
    event.feature_flags['show_schedule'] = True
    event.save(update_fields=['talks_published', 'feature_flags'])


def _unpublish_schedule(event):
    event.feature_flags['show_schedule'] = False
    event.talks_published = True
    event.save(update_fields=['feature_flags', 'talks_published'])


@pytest.mark.django_db
def test_public_stars_include_schedule_metadata_when_schedule_is_public(client, event, slot, track, user):
    with scope(event=event):
        slot.submission.track = track
        slot.submission.save(update_fields=['track'])
        _publish_user(user)
        _publish_talk_pages(event)
        SubmissionFavourite.objects.create(user=user, submission=slot.submission)

    cache.clear()
    response = client.get(_stars_url(event), HTTP_ACCEPT='text/html')
    assert response.status_code == 200
    payload = json.loads(response.context['schedule_json'])
    talk = next(item for item in payload['talks'] if item['code'] == slot.submission.code)
    assert talk['start']
    assert talk['end']
    assert talk['room'] == slot.room_id
    assert talk['track'] == track.pk
    assert talk.get('schedule_pending') is not True
    assert payload['rooms']
    assert payload['tracks']
    assert 'Testroom' in response.text
    assert 'Test Track' in response.text


@pytest.mark.django_db
def test_public_stars_hide_unpublished_schedule_metadata(client, event, slot, other_slot, track, user):
    with scope(event=event):
        slot.submission.track = track
        slot.submission.save(update_fields=['track'])
        _publish_user(user)
        SubmissionFavourite.objects.create(user=user, submission=slot.submission)
        _unpublish_schedule(event)

    cache.clear()
    response = client.get(_stars_url(event), HTTP_ACCEPT='text/html')
    assert response.status_code == 200
    payload = json.loads(response.context['schedule_json'])
    assert [item['code'] for item in payload['talks']] == [slot.submission.code]
    talk = payload['talks'][0]
    assert talk['title'] == slot.submission.title
    assert talk['start'] is None
    assert talk['end'] is None
    assert talk['room'] is None
    assert talk['track'] is None
    assert talk['schedule_pending'] is True
    assert payload['rooms'] == []
    assert payload['tracks'] == []
    assert 'Testroom' not in response.text
    assert 'Test Track' not in response.text
    assert other_slot.submission.title not in response.text

    favs = client.get(_stars_url(event).rstrip('/') + '.json')
    assert favs.status_code == 200
    assert favs.json()['favs'] == [slot.submission.code]


@pytest.mark.django_db
def test_organizer_still_sees_unpublished_schedule_on_public_stars(orga_client, event, slot, track, user):
    with scope(event=event):
        slot.submission.track = track
        slot.submission.save(update_fields=['track'])
        _publish_user(user)
        SubmissionFavourite.objects.create(user=user, submission=slot.submission)
        _unpublish_schedule(event)

    cache.clear()
    response = orga_client.get(_stars_url(event), HTTP_ACCEPT='text/html')
    assert response.status_code == 200
    payload = json.loads(response.context['schedule_json'])
    talk = next(item for item in payload['talks'] if item['code'] == slot.submission.code)
    assert talk['start']
    assert talk['room'] == slot.room_id
    assert talk['track'] == track.pk
    assert payload['rooms']
    assert 'Testroom' in response.text
