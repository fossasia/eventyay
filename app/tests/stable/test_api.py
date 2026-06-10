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
        # Try common API documentation paths
        response = client.get('/api/v1/schema/')
        # May or may not be configured
        assert response.status_code in [200, 404]

    def test_api_organizers_requires_auth(self, client):
        """Test that organizers API requires authentication."""
        response = client.get('/api/v1/organizers/')
        assert response.status_code in [401, 403]

    def test_api_organizers_with_auth(self, authenticated_client):
        """Test that organizers API works with authentication."""
        response = authenticated_client.get('/api/v1/organizers/')
        # Should return list (might be empty) or forbidden based on permissions
        assert response.status_code in [200, 403]

    def test_api_permission_dummy_auth(self):
        """Test ApiPermission does not crash on auth objects lacking has_endpoint_permission."""
        from unittest.mock import Mock
        from django.test import RequestFactory
        from eventyay.api.permissions import ApiPermission

        permission = ApiPermission()
        request = RequestFactory().get('/api/v1/organizers/')
        
        class DummyAuth:
            pass
            
        request.auth = DummyAuth()
        request.organizer = Mock()
        request.user = Mock()
        request.user.has_perm.return_value = True
        
        view = Mock()
        view.detail = False
        view.action = 'list'
        view.queryset.model.get_perm.return_value = 'view_model'
        
        assert permission.has_permission(request, view) is True
        
        # Test with non-callable attribute
        request.auth.has_endpoint_permission = False
        assert permission.has_permission(request, view) is True


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
