import json

import pytest
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.agenda.views.speaker import SpeakerList
from eventyay.agenda.views.utils import matching_content_locales
from eventyay.base.models import SpeakerProfile, SpeakerSocialLink, Submission


def _publish_speakers_page(event):
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])


def _speakers_json(client, event, **params):
    params = {'format': 'json', **params}
    response = client.get(event.urls.speakers, params)
    assert response.status_code == 200
    return response.json()


def test_matching_content_locales_normalizes_region():
    assert set(matching_content_locales(['en'], ['en-us', 'de'])) == {'en', 'en-us'}
    assert set(matching_content_locales(['en-US'], ['en', 'en-us', 'de'])) == {'en-US', 'en', 'en-us'}


@pytest.mark.django_db
def test_speakers_overview_html_has_meta_not_full_schedule(client, event, speaker, slot):
    _publish_speakers_page(event)
    response = client.get(event.urls.speakers, follow=True)
    assert response.status_code == 200
    assert 'pretalx-schedule-data' not in response.text
    assert 'pretalx-speakers-meta' in response.text
    assert 'view="speakers"' in response.text
    meta = json.loads(response.context['speakers_meta_json'])
    assert meta['timezone'] == event.timezone


@pytest.mark.django_db
def test_speakers_json_keeps_session_and_profile_fields(client, event, speaker, slot, track):
    _publish_speakers_page(event)
    with scope(event=event):
        event.cfp.fields['social_links'] = {'visibility': 'optional', 'public': True}
        event.cfp.save()
        slot.submission.track = track
        slot.submission.content_locale = 'en-us'
        slot.submission.save()
        profile = speaker.event_profile(event)
        SpeakerSocialLink.objects.create(
            profile=profile,
            network='github',
            url='https://github.com/octocat',
        )

    payload = _speakers_json(client, event)
    assert payload['next'] is None
    card = next(item for item in payload['results'] if item['code'] == speaker.code)
    assert card['name'] == speaker.fullname
    assert card['featured_position'] is None
    assert card['biography'] == 'Best speaker in the world.'
    assert card['avatar_thumbnail_tiny'] is None
    assert card['avatar_thumbnail_default'] is None
    assert card['social_links'][0]['url'] == 'https://github.com/octocat'
    session = card['sessions'][0]
    assert session['id'] == slot.submission.code
    assert session['slot_id'] == slot.pk
    assert session['title'] == slot.submission.title
    assert session['start']
    assert session['end']
    assert session['content_locale'] == 'en-us'
    assert session['track']['id'] == str(track.pk)
    assert session['track']['color'] == track.color
    assert session['room']['id'] == str(slot.room.pk)
    assert session['room']['name']


@pytest.mark.django_db
def test_speakers_json_hides_private_biography(client, event, speaker, slot):
    _publish_speakers_page(event)
    with scope(event=event):
        fields = dict(event.cfp.fields)
        biography = dict(fields.get('biography') or {})
        biography['public'] = False
        fields['biography'] = biography
        event.cfp.fields = fields
        event.cfp.save()

    payload = _speakers_json(client, event, q='Best speaker')
    assert payload['results'] == []
    card = next(item for item in _speakers_json(client, event)['results'] if item['code'] == speaker.code)
    assert card['biography'] == ''


@pytest.mark.django_db
def test_speakers_json_search_matches_visible_title_and_name(client, event, speaker, slot):
    _publish_speakers_page(event)
    by_name = _speakers_json(client, event, q='Jane')
    assert {item['code'] for item in by_name['results']} == {speaker.code}
    by_title = _speakers_json(client, event, q='Lametta')
    assert {item['code'] for item in by_title['results']} == {speaker.code}


@pytest.mark.django_db
def test_speakers_json_search_ignores_other_event_titles(client, event, speaker, slot, other_event):
    _publish_speakers_page(event)
    unique_title = 'UNIQUE_OTHER_EVENT_TITLE_XYZ'
    with scope(event=other_event):
        SpeakerProfile.objects.create(user=speaker, event=other_event, biography='other bio')
        submission = Submission.objects.create(
            title=unique_title,
            event=other_event,
            submission_type=other_event.cfp.default_type,
            content_locale='en',
        )
        submission.speakers.add(speaker)
        submission.accept()
        submission.confirm()
        other_event.release_schedule('v1')
        other_event.talks_published = True
        other_event.save(update_fields=['talks_published'])

    payload = _speakers_json(client, event, q=unique_title)
    assert payload['results'] == []


@pytest.mark.django_db
def test_speakers_json_search_ignores_unpublished_titles(client, event, speaker, slot):
    _publish_speakers_page(event)
    hidden_title = 'HIDDEN_TALK_TITLE_ZZZ'
    with scope(event=event):
        submission = Submission.objects.create(
            title=hidden_title,
            event=event,
            submission_type=event.cfp.default_type,
            content_locale='en',
        )
        submission.speakers.add(speaker)

    payload = _speakers_json(client, event, q=hidden_title)
    assert payload['results'] == []


@pytest.mark.django_db
def test_speakers_json_language_filter_matches_locale_variants(client, event, speaker, slot):
    _publish_speakers_page(event)
    with scope(event=event):
        slot.submission.content_locale = 'en-us'
        slot.submission.save()

    payload = _speakers_json(client, event, language='en')
    assert {item['code'] for item in payload['results']} == {speaker.code}


@pytest.mark.django_db
def test_speakers_json_track_filter_and_string_ids(client, event, speaker, slot, track, other_track):
    _publish_speakers_page(event)
    with scope(event=event):
        slot.submission.track = track
        slot.submission.save()

    matching = _speakers_json(client, event, track=str(track.pk))
    assert {item['code'] for item in matching['results']} == {speaker.code}
    empty = _speakers_json(client, event, track=str(other_track.pk))
    assert empty['results'] == []

    html = client.get(event.urls.speakers, follow=True)
    meta = json.loads(html.context['speakers_meta_json'])
    assert str(track.pk) in {item['id'] for item in meta['tracks']}
    assert str(other_track.pk) not in {item['id'] for item in meta['tracks']}


@pytest.mark.django_db
def test_speakers_json_serializes_i18n_track_and_room_names(client, event, speaker, slot, track):
    _publish_speakers_page(event)
    with scope(event=event):
        track.name = LazyI18nString({'en': 'English Track', 'de': 'Deutscher Track'})
        track.save()
        slot.submission.track = track
        slot.submission.save()

    payload = _speakers_json(client, event)
    session = next(item for item in payload['results'] if item['code'] == speaker.code)['sessions'][0]
    name = session['track']['name']
    if isinstance(name, dict):
        assert name.get('en') == 'English Track'
    else:
        assert 'English Track' in str(name)


@pytest.mark.django_db
def test_speakers_html_does_not_switch_on_json_accept_header(client, event, speaker, slot):
    _publish_speakers_page(event)
    response = client.get(event.urls.speakers, HTTP_ACCEPT='application/json')
    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/html')


@pytest.mark.django_db
def test_speakers_json_omits_unnamed_speaker_email(client, event, speaker, slot):
    _publish_speakers_page(event)
    with scope(event=event):
        speaker.fullname = ''
        speaker.save(update_fields=['fullname'])

    card = next(item for item in _speakers_json(client, event)['results'] if item['code'] == speaker.code)
    assert card['name'] is None
    assert speaker.email not in json.dumps(card)


@pytest.mark.django_db
def test_speakers_json_hides_private_content_locale(client, event, speaker, slot):
    _publish_speakers_page(event)
    with scope(event=event):
        slot.submission.content_locale = 'en-us'
        slot.submission.save()
        fields = dict(event.cfp.fields)
        content_locale = dict(fields.get('content_locale') or {})
        content_locale['public'] = False
        fields['content_locale'] = content_locale
        event.cfp.fields = fields
        event.cfp.save()

    payload = _speakers_json(client, event, language='en')
    card = next(item for item in payload['results'] if item['code'] == speaker.code)
    assert card['sessions'][0]['content_locale'] == ''
    html = client.get(event.urls.speakers, follow=True)
    meta = json.loads(html.context['speakers_meta_json'])
    assert meta['content_locales'] == []


@pytest.mark.django_db
def test_speakers_json_next_url_is_absolute(client, event, speaker, other_speaker, slot, monkeypatch):
    _publish_speakers_page(event)
    monkeypatch.setattr(SpeakerList, 'paginate_by', 1)
    with scope(event=event):
        slot.submission.speakers.add(other_speaker)

    payload = _speakers_json(client, event)
    assert payload['next']
    assert payload['next'].startswith('http')
    assert 'format=json' in payload['next']
    assert 'page=2' in payload['next']
