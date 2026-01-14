import json
import pytest
from django_scopes import scope

@pytest.mark.django_db
def test_orga_can_toggle_featured_speaker(orga_client, speaker, event):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.toggle_featured
        assert not speaker.event_profile(event).is_featured
    
    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert response.json()['status'] == 'success'
    assert response.json()['is_featured'] is True
    
    with scope(event=event):
        speaker.refresh_from_db()
        assert speaker.event_profile(event).is_featured

    response = orga_client.post(url, follow=True)
    assert response.status_code == 200
    assert response.json()['status'] == 'success'
    assert response.json()['is_featured'] is False
    
    with scope(event=event):
        speaker.refresh_from_db()
        assert not speaker.event_profile(event).is_featured


@pytest.mark.django_db
def test_reviewer_cannot_toggle_featured_speaker(review_client, speaker, event):
    with scope(event=event):
        url = speaker.event_profile(event).orga_urls.toggle_featured
    
    response = review_client.post(url, follow=True)
    assert response.status_code == 404
    
    with scope(event=event):
        speaker.refresh_from_db()
        assert not speaker.event_profile(event).is_featured


@pytest.mark.django_db
def test_orga_can_reorder_speakers(orga_client, speaker, event, other_speaker):
    with scope(event=event):
        p1 = speaker.event_profile(event)
        p2 = other_speaker.event_profile(event)
        p1.is_featured = True
        p2.is_featured = True
        p1.save()
        p2.save()
        url = event.orga_urls.speakers + "reorder/"
    
    data = {
        'speaker_ids': [p2.id, p1.id]
    }
    response = orga_client.post(
        url,
        data=json.dumps(data),
        content_type='application/json',
        follow=True
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'success'
    
    with scope(event=event):
        p1.refresh_from_db()
        p2.refresh_from_db()
        assert p2.featured_order == 0
        assert p1.featured_order == 1


@pytest.mark.django_db
def test_orga_reorder_invalid_ids(orga_client, event):
    url = event.orga_urls.speakers + "reorder/"
    data = {
        'speaker_ids': [99999]
    }
    response = orga_client.post(
        url,
        data=json.dumps(data),
        content_type='application/json',
        follow=True
    )
    assert response.status_code == 400
    assert response.json()['status'] == 'error'
