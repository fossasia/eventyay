"""
Tests for the speaker profile view fix (issue #2635).

These tests validate that speakers can access their profile pages
even if they don't have an explicit SpeakerProfile record before the
fix creates one automatically.
"""
import pytest
from django_scopes import scope

from eventyay.base.models import SpeakerProfile


@pytest.mark.django_db
def test_speaker_profile_page_accessible_without_existing_profile(client, event, slot):
    """Test that a speaker's profile page is accessible even without a pre-existing SpeakerProfile."""
    # Setup: Create a speaker in a talk but don't explicitly create their profile
    speaker = slot.submission.speakers.first()

    with scope(event=event):
        # Make sure talks are published so speakers are viewable
        event.talks_published = True
        event.save(update_fields=['talks_published'])

        # Delete the profile to simulate the issue
        SpeakerProfile.objects.filter(user=speaker, event=event).delete()

        # Verify profile doesn't exist
        assert not SpeakerProfile.objects.filter(user=speaker, event=event).exists()

    # Access the speaker profile page
    speaker_profile_url = f"{event.urls.base}speakers/{speaker.code}/"
    response = client.get(speaker_profile_url, follow=True)

    # Should succeed with 200 status
    assert response.status_code == 200
    assert speaker.fullname in response.text or speaker.code in response.text

    # Verify profile was auto-created
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(user=speaker, event=event).first()
        assert profile is not None
        assert profile.user == speaker
        assert profile.event == event


@pytest.mark.django_db
def test_speaker_profile_maintains_existing_profile_data(client, event, slot):
    """Test that auto-created profiles don't overwrite existing profile data."""
    speaker = slot.submission.speakers.first()

    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])

        # Create profile with specific data
        profile = SpeakerProfile.objects.get(user=speaker, event=event)
        profile.biography = "Test biography"
        profile.is_featured = True
        profile.position = 5
        profile.save()

    # Access the page
    speaker_profile_url = f"{event.urls.base}speakers/{speaker.code}/"
    response = client.get(speaker_profile_url, follow=True)

    assert response.status_code == 200

    # Verify profile data is preserved
    with scope(event=event):
        profile = SpeakerProfile.objects.get(user=speaker, event=event)
        assert profile.biography == "Test biography"
        assert profile.is_featured is True
        assert profile.position == 5


@pytest.mark.django_db
def test_speaker_ical_export_works_without_existing_profile(client, event, slot):
    """Test that speaker iCal export works with auto-created profile."""
    speaker = slot.submission.speakers.first()

    with scope(event=event):
        event.talks_published = True
        event.save(update_fields=['talks_published'])

        # Delete profile to simulate the issue
        SpeakerProfile.objects.filter(user=speaker, event=event).delete()

    # Access the iCal export
    ical_url = f"{event.urls.base}speakers/{speaker.code}/talks.ics"
    response = client.get(ical_url, follow=True)

    # Should succeed
    assert response.status_code == 200
    assert response['Content-Type'] == 'text/calendar'

    # Verify profile was auto-created
    with scope(event=event):
        profile = SpeakerProfile.objects.filter(user=speaker, event=event).first()
        assert profile is not None
