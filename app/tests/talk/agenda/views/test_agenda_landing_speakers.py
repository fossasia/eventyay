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
    assert response.text.index(other_speaker.fullname) < response.text.index(
        speaker.fullname
    )
    assert '<details class="featured-speaker-card">' in response.text
    assert 'featured-speaker-sessions' in response.text
    assert slot.submission.title in response.text
    assert other_slot.submission.title in response.text
    assert 'More speakers' in response.text
    assert 'class="btn btn-info btn-sm"' in response.text
    assert f'href="{event.urls.speakers}"' in response.text


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
    assert 'More speakers' not in response.text
