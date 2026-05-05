"""
Tests for public presale/event pages (agenda, schedule, speakers).
These pages should be accessible without authentication.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from eventyay.base.models import Event


@pytest.mark.django_db
class TestPresalePages:
    """Test public event pages accessible via presale URLs."""

    def test_index_page_loads(self, client):
        """Test that the main index page loads."""
        response = client.get('/')
        # Should either show landing or redirect
        assert response.status_code in [200, 301, 302]

    def test_locale_set_endpoint(self, client):
        """Test locale setting endpoint exists."""
        response = client.get('/locale/set?locale=en&next=/')
        # Should redirect after setting locale
        assert response.status_code in [302, 200]


@pytest.mark.django_db
class TestEventPages:
    """Test event-specific public pages."""

    def test_event_landing_page(self, client, organizer, event):
        """Test that event landing page loads for valid event."""
        url = f'/{organizer.slug}/{event.slug}/'
        response = client.get(url)
        # Should return 200 for a valid public event or redirect
        assert response.status_code in [200, 301, 302]

    def test_invalid_organizer_slug(self, client, event):
        """Test that an invalid organizer slug returns 404."""
        url = f'/nonexistent-organizer/{event.slug}/'
        response = client.get(url)
        assert response.status_code == 404

    def test_invalid_event_slug(self, client, organizer):
        """Test that an invalid event slug returns 404."""
        url = f'/{organizer.slug}/nonexistent-event/'
        response = client.get(url)
        assert response.status_code == 404

    def test_invalid_organizer_and_event_slug(self, client):
        """Test that both invalid organizer and event slugs return 404."""
        url = '/nonexistent-organizer/nonexistent-event/'
        response = client.get(url)
        assert response.status_code == 404

    def test_robots_txt(self, client):
        """Test that robots.txt is accessible."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert 'text/plain' in response['Content-Type']

    def test_organizer_page_hides_excluded_start_page_events(self, client, organizer, event):
        """Events excluded from organizer start page should not be listed."""
        visible_event = event
        visible_event.name = 'Visible Organizer Event'
        visible_event.save(update_fields=['name'])

        hidden_event = Event.objects.create(
            organizer=organizer,
            name='Hidden Organizer Event',
            slug='hidden-organizer-event',
            date_from=timezone.now() + timedelta(days=30),
            date_to=timezone.now() + timedelta(days=31),
            currency='USD',
            locale='en',
            is_public=True,
            live=True,
            email='hidden@example.com',
        )
        hidden_event.display_settings['exclude_from_start_page'] = True
        hidden_event.save(update_fields=['display_settings'])

        response = client.get(f'/{organizer.slug}/')

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Visible Organizer Event' in content
        assert 'Hidden Organizer Event' not in content


@pytest.mark.django_db
class TestAgendaPages:
    """Test agenda/schedule pages."""

    def test_schedule_view_exists(self, client, organizer, event):
        """Test schedule page URL pattern."""
        url = f'/agenda/{organizer.slug}/{event.slug}/schedule/'
        response = client.get(url)
        # May 404 if schedule not configured, but shouldn't 500
        assert response.status_code in [200, 404]

    def test_speaker_list_exists(self, client, organizer, event):
        """Test speaker list page URL pattern."""
        url = f'/agenda/{organizer.slug}/{event.slug}/speaker/'
        response = client.get(url)
        # May 404 if speakers not configured, but shouldn't 500
        assert response.status_code in [200, 404]


@pytest.mark.django_db
class TestPlatformSearch:
    def test_internal_event_picker_returns_all_matching_events(self, organizer_client, organizer, event):
        """The internal /common/events/search/ endpoint is an authenticated event picker,
        not a public search; it returns all matching events regardless of exclude_from_search."""
        event.name = 'Visible Search Event'
        event.save(update_fields=['name'])

        hidden_event = Event.objects.create(
            organizer=organizer,
            name='Hidden Search Event',
            slug='hidden-search-event',
            date_from=timezone.now() + timedelta(days=30),
            date_to=timezone.now() + timedelta(days=31),
            currency='USD',
            locale='en',
            is_public=True,
            live=True,
            email='hidden-search@example.com',
        )
        hidden_event.display_settings['exclude_from_search'] = True
        hidden_event.save(update_fields=['display_settings'])

        response = organizer_client.get('/common/events/search/?query=Search')
        assert response.status_code == 200
        payload = response.json()
        names = {row['name'] for row in payload}
        assert 'Visible Search Event' in names
        assert 'Hidden Search Event' in names

@pytest.mark.django_db
class TestStartPageVisibility:
    """Test visibility and search exclusion on the platform start page."""

    def test_start_page_hides_excluded_events(self, client, organizer, event):
        """Events excluded from start page should not appear in the upcoming list."""
        event.name = 'Visible Start Event'
        event.save(update_fields=['name'])

        hidden_event = Event.objects.create(
            organizer=organizer,
            name='Hidden Start Event',
            slug='hidden-start-event',
            date_from=timezone.now() + timedelta(days=30),
            date_to=timezone.now() + timedelta(days=31),
            currency='USD',
            locale='en',
            is_public=True,
            live=True,
            startpage_visible=True,
            email='hidden-start@example.com',
        )
        hidden_event.display_settings['exclude_from_start_page'] = True
        hidden_event.save(update_fields=['display_settings'])

        response = client.get('/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Visible Start Event' in content
        assert 'Hidden Start Event' not in content

    def test_start_page_search_excludes_hidden_events(self, client, organizer, event):
        """Events excluded from search should not appear in start page search results."""
        event.name = 'Visible Search Event'
        event.save(update_fields=['name'])

        hidden_event = Event.objects.create(
            organizer=organizer,
            name='Hidden Search Event',
            slug='hidden-search-event',
            date_from=timezone.now() + timedelta(days=30),
            date_to=timezone.now() + timedelta(days=31),
            currency='USD',
            locale='en',
            is_public=True,
            live=True,
            email='hidden-search@example.com',
        )
        hidden_event.display_settings['exclude_from_search'] = True
        hidden_event.save(update_fields=['display_settings'])

        response = client.get('/?q=Search')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Visible Search Event' in content
        assert 'Hidden Search Event' not in content
