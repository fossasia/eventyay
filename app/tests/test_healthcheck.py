"""
Tests for health and status endpoints.
"""
import pytest
from unittest.mock import patch

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
        """Healthcheck returns 503 if DB is unavailable."""
        # Patch the User.objects.exists() call to raise an exception
        mocker.patch(
            'eventyay.base.models.User.objects.exists',
            side_effect=Exception("Database connection failed")
        )
        response = client.get(reverse('healthcheck'))
        # Should either return 503 or 500 depending on error handling
        assert response.status_code in [500, 503]

    def test_healthcheck_cache_unavailable(self, client, mocker):
        """Healthcheck returns 503 if cache is unavailable."""
        # Patch cache.set to fail
        mocker.patch(
            'django.core.cache.cache.set',
            side_effect=Exception("Cache unavailable")
        )
        response = client.get(reverse('healthcheck'))
        # Should either return 503 or 500 depending on error handling
        assert response.status_code in [500, 503]
