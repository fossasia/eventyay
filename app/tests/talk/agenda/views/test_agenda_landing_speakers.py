import json
import re
from urllib.parse import urlparse

import pytest
from django.urls import reverse
from django_scopes import scope

from eventyay.talk_rules.agenda import is_pre_agenda_featured_public, is_speaker_viewable


def _enable_public_featured_speakers(event):
    with scope(event=event):
        event.talks_published = False
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])


@pytest.mark.django_db
def test_landing_page_shows_featured_speakers_in_custom_order(
    client, event, slot, other_slot, speaker, other_speaker
):
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])
        first_profile = speaker.event_profile(event)
        second_profile = other_speaker.event_profile(event)
        first_profile.is_featured = True
        first_profile.position = 1
        first_profile.save(update_fields=['is_featured', 'position'])
        second_profile.is_featured = True
        second_profile.position = 0
        second_profile.save(update_fields=['is_featured', 'position'])

    response = client.get(event.urls.base)

    assert response.status_code == 200
    assert 'Featured Speakers' in response.text

    widget_schedule = response.context['featured_speakers_widget_schedule']
    assert widget_schedule is not None
    speakers_by_code = {s['code']: s for s in widget_schedule['speakers']}
    assert set(speakers_by_code.keys()) >= {other_speaker.code, speaker.code}
    assert speakers_by_code[speaker.code]['is_featured'] is True
    assert speakers_by_code[speaker.code]['featured_position'] == 1
    assert speakers_by_code[other_speaker.code]['is_featured'] is True
    assert speakers_by_code[other_speaker.code]['featured_position'] == 0

    talk_codes = {t['code'] for t in widget_schedule['talks']}
    assert {
        other_slot.submission.code,
        slot.submission.code,
    }.issubset(talk_codes)
    speaker_codes = [s['code'] for s in widget_schedule['speakers']]
    assert speaker_codes.index(other_speaker.code) < speaker_codes.index(speaker.code)
    assert 'pretalx-schedule-data' in response.text
    assert 'view="featured-speakers"' in response.text
    assert response.context['featured_speakers_widget_schedule']['speakers_list_public'] is True


@pytest.mark.django_db
def test_landing_page_featured_speakers_use_profile_order_without_agenda(
    client, event, speaker, other_speaker
):
    _enable_public_featured_speakers(event)
    with scope(event=event):
        first_profile = speaker.event_profile(event)
        second_profile = other_speaker.event_profile(event)
        first_profile.is_featured = True
        first_profile.position = 2
        first_profile.save(update_fields=['is_featured', 'position'])
        second_profile.is_featured = True
        second_profile.position = 0
        second_profile.save(update_fields=['is_featured', 'position'])

    response = client.get(event.urls.base)

    assert response.status_code == 200
    widget_schedule = response.context['featured_speakers_widget_schedule']
    speaker_codes = [s['code'] for s in widget_schedule['speakers']]
    assert speaker_codes == [other_speaker.code, speaker.code]
    assert widget_schedule['speakers_list_public'] is False


@pytest.mark.django_db
def test_landing_page_shows_more_speakers_link_when_agenda_is_public(
    client, event, slot, speaker
):
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])

    response = client.get(event.urls.base)

    assert response.status_code == 200
    assert response.context['featured_speakers_widget_schedule']['speakers_list_public'] is True


@pytest.mark.django_db
def test_landing_page_shows_featured_speakers_with_after_schedule_before_release(
    client, event, speaker
):
    with scope(event=event):
        event.talks_published = False
        event.feature_flags['show_featured_speakers'] = 'after_schedule'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.position = 0
        profile.save(update_fields=['is_featured', 'position'])
        assert event.current_schedule is None

    response = client.get(event.urls.base)

    assert response.status_code == 200
    assert 'view="featured-speakers"' in response.text
    widget_schedule = response.context['featured_speakers_widget_schedule']
    assert {s['code'] for s in widget_schedule['speakers']} == {speaker.code}
    assert widget_schedule['speakers_list_public'] is False


@pytest.mark.django_db
def test_speakers_page_lists_all_speakers_after_schedule_release(
    client, event, slot, other_slot, speaker, other_speaker
):
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])
        speaker.event_profile(event)
        other_speaker.event_profile(event)

    response = client.get(event.urls.speakers, follow=True)

    assert response.status_code == 200
    schedule_data = json.loads(response.context['schedule_json'])
    assert {s['code'] for s in schedule_data['speakers']} >= {speaker.code, other_speaker.code}


@pytest.mark.django_db
def test_landing_page_hides_featured_speakers_when_none_are_marked(
    client, event, slot
):
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])

    response = client.get(event.urls.base)

    assert response.status_code == 200
    assert 'Featured Speakers' not in response.text
    assert 'pretalx-schedule-data' not in response.text
    assert 'view="featured-speakers"' not in response.text


@pytest.mark.django_db
def test_landing_page_shows_featured_speaker_not_on_published_schedule_with_coming_soon(
    client, event, slot, speaker, other_speaker, other_accepted_submission
):
    """Featured speakers stay on the landing page with coming-soon sessions when not scheduled."""
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.save(update_fields=['talks_published', 'feature_flags'])
        profile = other_speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])
        event.release_schedule('v1')
        published_codes = set(event.speakers.values_list('code', flat=True))
        assert speaker.code in published_codes
        assert other_speaker.code not in published_codes

    response = client.get(event.urls.base)

    assert response.status_code == 200
    widget_schedule = response.context['featured_speakers_widget_schedule']
    assert other_speaker.code in {s['code'] for s in widget_schedule['speakers']}
    other_talks = [
        talk
        for talk in widget_schedule['talks']
        if other_speaker.code in talk.get('speakers', [])
    ]
    assert len(other_talks) == 1
    assert other_talks[0]['code'] == other_accepted_submission.code
    assert other_talks[0]['schedule_pending'] is True


@pytest.mark.django_db
def test_landing_page_shows_featured_speakers_as_coming_soon_when_released_schedule_has_no_sessions(
    client, event, slot, speaker, confirmed_submission
):
    """Featured speakers stay on the info page; nav and speakers list hide when the schedule is empty."""
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_schedule'] = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.save(update_fields=['talks_published', 'feature_flags'])
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])
        event.release_schedule('v1')
        assert event.speakers.exists()

        for talk in event.wip_schedule.talks.all():
            talk.delete()
        event.release_schedule('v2')
        event.__dict__.pop('speakers', None)
        event.__dict__.pop('has_schedule_content', None)
        event.__dict__.pop('current_schedule', None)
        assert not event.speakers.exists()

    landing = client.get(event.urls.base)
    assert landing.status_code == 200
    assert 'view="featured-speakers"' in landing.text
    widget_schedule = landing.context['featured_speakers_widget_schedule']
    assert widget_schedule is not None
    assert {s['code'] for s in widget_schedule['speakers']} == {speaker.code}
    assert widget_schedule['speakers_list_public'] is False
    assert len(widget_schedule['talks']) == 1
    assert widget_schedule['talks'][0]['code'] == confirmed_submission.code
    assert widget_schedule['talks'][0]['schedule_pending'] is True
    speakers_nav_pattern = re.compile(
        rf'<a href="{re.escape(str(event.urls.speakers))}" class="header-tab'
    )
    assert speakers_nav_pattern.search(landing.content.decode()) is None

    speakers_list = client.get(event.urls.speakers, follow=True)
    assert speakers_list.status_code == 200
    assert speakers_list.request['PATH_INFO'].rstrip('/') == urlparse(str(event.urls.base)).path.rstrip('/')


@pytest.mark.django_db
def test_featured_speaker_links_work_without_published_schedule(client, event, speaker):
    _enable_public_featured_speakers(event)
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])
        assert event.current_schedule is None

    landing = client.get(event.urls.base)
    assert landing.status_code == 200
    assert 'view="featured-speakers"' in landing.text
    widget_schedule = landing.context['featured_speakers_widget_schedule']
    assert widget_schedule['talks'] == []

    speaker_url = reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug})
    speaker_response = client.get(speaker_url, follow=True)
    assert speaker_response.status_code == 200
    assert speaker.fullname in speaker_response.text
    assert 'pretalx-schedule-data' in speaker_response.text
    schedule_data = json.loads(speaker_response.context['schedule_json'])
    assert schedule_data['talks'] == []
    assert {s['code'] for s in schedule_data['speakers']} == {speaker.code}
    assert list(speaker_response.context['talks']) == []

    speakers_list_response = client.get(event.urls.speakers, follow=True)
    assert speakers_list_response.status_code == 404

    talk_url = reverse(
        'agenda:talk.detail',
        kwargs={'slug': 'nonexistent', 'event': event.slug},
    )
    assert client.get(talk_url).status_code == 404


@pytest.mark.django_db
def test_featured_speakers_show_pending_sessions_before_agenda_is_public(
    client, event, slot, speaker
):
    _enable_public_featured_speakers(event)
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])

    landing = client.get(event.urls.base)
    assert landing.status_code == 200
    widget_schedule = landing.context['featured_speakers_widget_schedule']
    assert len(widget_schedule['talks']) == 1
    assert widget_schedule['talks'][0]['code'] == slot.submission.code
    assert widget_schedule['talks'][0]['schedule_pending'] is True
    assert widget_schedule['talks'][0]['start'] is None


@pytest.mark.django_db
def test_featured_speakers_show_pending_sessions_in_private_talk_testmode(
    client, event, slot, speaker
):
    with scope(event=event):
        event.talks_published = True
        event.private_testmode = True
        event.settings.private_testmode_talks = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'private_testmode', 'feature_flags'])
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])

    landing = client.get(event.urls.base)
    assert landing.status_code == 200
    widget_schedule = landing.context['featured_speakers_widget_schedule']
    assert len(widget_schedule['talks']) == 1
    assert widget_schedule['talks'][0]['code'] == slot.submission.code
    assert widget_schedule['talks'][0]['schedule_pending'] is True
    assert widget_schedule['talks'][0]['start'] is None

    speaker_response = client.get(
        reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug}),
        follow=True,
    )
    assert speaker_response.status_code == 200
    speaker_schedule = json.loads(speaker_response.context['schedule_json'])
    assert len(speaker_schedule['talks']) == 1
    assert speaker_schedule['talks'][0]['schedule_pending'] is True
    assert speaker_schedule['talks'][0]['start'] is None


@pytest.mark.django_db
def test_featured_submission_visible_on_speaker_profile_before_public_release(
    client, event, slot, speaker
):
    """Featured sessions show as coming soon on the speaker profile before public release."""
    with scope(event=event):
        event.talks_published = False
        event.feature_flags['show_featured'] = 'always'
        event.feature_flags['show_featured_speakers'] = 'never'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])
        slot.submission.is_featured = True
        slot.submission.save(update_fields=['is_featured'])
        assert speaker.event_profile(event).is_featured is False

    speaker_response = client.get(
        reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug}),
        follow=True,
    )
    assert speaker_response.status_code == 200
    speaker_schedule = json.loads(speaker_response.context['schedule_json'])
    assert len(speaker_schedule['talks']) == 1
    assert speaker_schedule['talks'][0]['code'] == slot.submission.code
    assert speaker_schedule['talks'][0]['schedule_pending'] is True


@pytest.mark.django_db
def test_featured_talk_detail_available_without_published_schedule(client, event, confirmed_submission):
    with scope(event=event):
        event.talks_published = False
        event.feature_flags['show_featured'] = 'always'
        event.save(update_fields=['talks_published', 'feature_flags'])
        confirmed_submission.is_featured = True
        confirmed_submission.save(update_fields=['is_featured'])
        assert event.current_schedule is None

    talk_url = reverse(
        'agenda:talk.detail',
        kwargs={'slug': confirmed_submission.code, 'event': event.slug},
    )
    response = client.get(talk_url, follow=True)
    assert response.status_code == 200
    schedule_data = json.loads(response.context['schedule_json'])
    assert schedule_data['talks'][0]['code'] == confirmed_submission.code
    assert schedule_data['talks'][0]['schedule_pending'] is True


@pytest.mark.django_db
def test_non_featured_speaker_profile_not_public_without_schedule(client, event, speaker):
    _enable_public_featured_speakers(event)
    with scope(event=event):
        assert event.current_schedule is None

    speaker_url = reverse('agenda:speaker', kwargs={'code': speaker.code, 'event': event.slug})
    response = client.get(speaker_url, follow=True)
    assert response.status_code == 403


@pytest.mark.django_db
def test_featured_speaker_not_duplicated_after_schedule_release(
    client, event, speaker, slot, other_speaker
):
    _enable_public_featured_speakers(event)
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])
        other_profile = other_speaker.event_profile(event)
        other_profile.is_featured = True
        other_profile.save(update_fields=['is_featured'])

    landing_before = client.get(event.urls.base)
    speakers_before = landing_before.context['featured_speakers_widget_schedule']['speakers']
    assert len([s for s in speakers_before if s['code'] == speaker.code]) == 1

    with scope(event=event):
        event.talks_published = True
        event.release_schedule('v1')

    landing_after = client.get(event.urls.base)
    speakers_after = landing_after.context['featured_speakers_widget_schedule']['speakers']
    assert len([s for s in speakers_after if s['code'] == speaker.code]) == 1


@pytest.mark.django_db
def test_featured_speaker_without_talks_still_viewable_after_schedule_release(
    client, event, speaker
):
    _enable_public_featured_speakers(event)
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])
        event.release_schedule('v1')
        event.talks_published = True
        event.save(update_fields=['talks_published'])

    with scope(event=event):
        assert is_pre_agenda_featured_public(None, event) is False
        assert is_speaker_viewable(None, profile) is True

    speaker_url = reverse(
        'agenda:speaker',
        kwargs={
            'code': speaker.code,
            'event': event.slug,
            'organizer': event.organizer.slug,
        },
    )
    response = client.get(speaker_url, follow=True)
    assert response.status_code == 200
    assert speaker.fullname in response.text


@pytest.mark.django_db
def test_featured_speaker_profile_is_viewable_without_published_schedule(event, speaker):
    _enable_public_featured_speakers(event)
    with scope(event=event):
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])
        assert is_pre_agenda_featured_public(None, event) is True
        assert is_speaker_viewable(None, profile) is True


@pytest.mark.django_db
def test_featured_speaker_profile_uses_schedule_rules_once_agenda_is_public(
    event, speaker, slot
):
    with scope(event=event):
        event.talks_published = True
        event.feature_flags['show_featured_speakers'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.save(update_fields=['talks_published', 'feature_flags'])
        profile = speaker.event_profile(event)
        profile.is_featured = True
        profile.save(update_fields=['is_featured'])

    with scope(event=event):
        assert is_speaker_viewable(None, profile) is True

    with scope(event=event):
        slot.is_visible = False
        slot.save()

    with scope(event=event):
        assert is_pre_agenda_featured_public(None, event) is False
        assert is_speaker_viewable(None, profile) is False
