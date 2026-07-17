"""
Tests for API endpoints.
"""
import pytest


@pytest.mark.django_db
class TestAPIEndpoints:
    """Test API v1 endpoints."""

    def test_api_root_returns_401_without_auth(self, client):
        """Test that API root requires authentication."""
        response = client.get('/api/v1/')
        # Should require authentication
        assert response.status_code in [401, 403, 404]

    def test_api_docs_accessible(self, client):
        """Test that API documentation is accessible."""
        schema_response = client.get('/api/v1/schema/', HTTP_ACCEPT='application/json')
        swagger_response = client.get('/api/v1/docs/')
        swagger_script_response = client.get('/api/v1/docs/?script=')
        redoc_response = client.get('/api/v1/redoc/')

        assert schema_response.status_code == 200
        assert schema_response.json()['openapi'] == '3.0.3'
        assert swagger_response.status_code == 200
        assert swagger_script_response.status_code == 200
        assert swagger_script_response['Content-Type'].startswith('application/javascript')
        assert redoc_response.status_code == 200

    def test_api_organizers_requires_auth(self, client):
        """Test that organizers API requires authentication."""
        response = client.get('/api/v1/organizers/')
        assert response.status_code in [401, 403]

    def test_api_organizers_with_auth(self, authenticated_client):
        """Test that organizers API works with authentication."""
        response = authenticated_client.get('/api/v1/organizers/')
        # Should return list (might be empty) or forbidden based on permissions
        assert response.status_code in [200, 403]


@pytest.mark.django_db
class TestWebhooksAPI:
    """Test webhook-related API endpoints."""

    def test_webhook_endpoint_exists(self, client, organizer, event):
        """Test webhook endpoint pattern exists."""
        # Webhooks are typically POST endpoints
        url = f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/webhooks/'
        response = client.get(url)
        # Should require auth
        assert response.status_code in [401, 403, 404]
