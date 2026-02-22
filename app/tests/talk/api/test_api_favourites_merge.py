import json

import pytest
from django_scopes import scope


@pytest.mark.django_db
def test_merge_favourites_unauthenticated(client, event, slot):
    url = event.api_urls.submissions + "favourites/merge/"
    response = client.post(
        url,
        data=json.dumps([slot.submission.code]),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_merge_favourites_schedule_not_public(event, speaker_client, slot):
    event.feature_flags["show_schedule"] = False
    event.save()

    url = event.api_urls.submissions + "favourites/merge/"
    response = speaker_client.post(
        url,
        data=json.dumps([slot.submission.code]),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_merge_favourites_empty_local(event, speaker_client, slot, speaker):
    """Merging empty local list returns server-side favs."""
    with scope(event=event):
        slot.submission.add_favourite(speaker)

    url = event.api_urls.submissions + "favourites/merge/"
    response = speaker_client.post(
        url,
        data=json.dumps([]),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert slot.submission.code in content


@pytest.mark.django_db
def test_merge_favourites_new_local(event, speaker_client, slot, speaker):
    """Local codes not on server get added."""
    url = event.api_urls.submissions + "favourites/merge/"
    response = speaker_client.post(
        url,
        data=json.dumps([slot.submission.code]),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert slot.submission.code in content
    # Verify persisted
    with scope(event=event):
        assert slot.submission.favourites.filter(user=speaker).exists()


@pytest.mark.django_db
def test_merge_favourites_dedup(event, speaker_client, slot, speaker):
    """Merging codes already on server doesn't duplicate."""
    with scope(event=event):
        slot.submission.add_favourite(speaker)

    url = event.api_urls.submissions + "favourites/merge/"
    response = speaker_client.post(
        url,
        data=json.dumps([slot.submission.code]),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert content.count(slot.submission.code) == 1


@pytest.mark.django_db
def test_merge_favourites_invalid_codes_ignored(event, speaker_client, slot):
    """Nonexistent codes are silently ignored."""
    url = event.api_urls.submissions + "favourites/merge/"
    response = speaker_client.post(
        url,
        data=json.dumps(["NONEXIST", slot.submission.code]),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 200
    content = json.loads(response.text)
    assert slot.submission.code in content
    assert "NONEXIST" not in content


@pytest.mark.django_db
def test_merge_favourites_bad_payload(event, speaker_client, slot):
    """Non-array payload returns 400."""
    url = event.api_urls.submissions + "favourites/merge/"
    response = speaker_client.post(
        url,
        data=json.dumps({"codes": [slot.submission.code]}),
        content_type="application/json",
        follow=True,
    )
    assert response.status_code == 400
