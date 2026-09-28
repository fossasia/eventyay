"""
Tests for health and status endpoints.
"""
import pytest

from django.db import DatabaseError
from django.urls import reverse


@pytest.mark.django_db
class TestHealthcheck:
    """Test the /healthcheck/ endpoint."""

    def test_healthcheck_returns_200(self, client):
        """Healthcheck should return 200 OK when services are available."""
        response = client.get(reverse('healthcheck'))
        assert response.status_code == 200

    def test_healthcheck_empty_body(self, client):
        """Healthcheck returns empty body on success."""
        response = client.get(reverse('healthcheck'))
        assert response.content == b''

    def test_healthcheck_content_type(self, client):
        """Healthcheck returns text/html content type."""
        response = client.get(reverse('healthcheck'))
        assert 'text/html' in response['Content-Type']

    def test_healthcheck_url_is_accessible(self, client):
        """Verify healthcheck is accessible at /healthcheck/."""
        response = client.get('/healthcheck/')
        assert response.status_code == 200

    def test_healthcheck_db_unavailable(self, client, mocker):
        """Healthcheck returns 503 when the database probe fails."""
        mocker.patch(
            'eventyay.base.models.User.objects.exists',
            side_effect=DatabaseError('Database connection failed'),
        )
        response = client.get(reverse('healthcheck'))
        assert response.status_code == 503
        assert response.content == b'Database not available.'

    def test_healthcheck_cache_unavailable(self, client, mocker):
        """Healthcheck returns 503 when the cache probe fails."""
        mocker.patch(
            'django.core.cache.cache.set',
            side_effect=Exception('Cache unavailable'),
        )
        response = client.get(reverse('healthcheck'))
        assert response.status_code == 503
        assert response.content == b'Cache not available.'
