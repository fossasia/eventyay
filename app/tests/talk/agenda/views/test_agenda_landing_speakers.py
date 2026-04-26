import pytest
from django_scopes import scope


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
    assert 'pretalx-schedule-data' in response.text
    assert 'view="featured-speakers"' in response.text


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
