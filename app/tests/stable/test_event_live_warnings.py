import pytest
from django.test import override_settings
from django.urls import reverse
from django_scopes import scopes_disabled

@pytest.fixture
def live_url(event):
    return reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )

@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_live_page_warnings_track_request(organizer_client, event, live_url):
    """An event requesting tracks but having 0 tracks gets a suggestion to add a track."""
    fields = dict(event.cfp.fields)
    fields['track'] = {'visibility': 'optional', 'public': True}
    event.cfp.fields = fields
    event.cfp.save()
    
    with scopes_disabled():
        event.tracks.all().delete()
    
    response = organizer_client.get(live_url)
    assert response.status_code == 200
    
    suggestions = response.context.get('suggestions', [])
    assert any("Add at least one track!" in str(s.get('text', '')) for s in suggestions)
