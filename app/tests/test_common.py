"""
Tests for common pages and utilities (redirects, CSP reporting, etc).
"""
import pytest
import json

from django.urls import reverse


@pytest.mark.django_db
class TestCommonPages:
    """Test common utility endpoints."""

    def test_redirect_endpoint_exists(self, client):
        """Test redirect utility endpoint."""
        response = client.get(reverse('redirect'))
        # Should handle redirect requests - returns 400 without proper params
        assert response.status_code in [200, 302, 400]

    def test_csp_report_endpoint(self, client):
        """Test CSP report endpoint accepts POST with valid JSON."""
        csp_report = {
            "csp-report": {
                "document-uri": "https://example.com/",
                "referrer": "",
                "blocked-uri": "https://evil.com/malicious.js",
                "violated-directive": "script-src",
                "original-policy": "script-src 'self'",
            }
        }
        response = client.post(
            reverse('csp.report'),
            data=json.dumps(csp_report),
            content_type='application/csp-report'
        )
        # Should accept CSP reports
        assert response.status_code in [200, 204]

    def test_csp_report_endpoint_empty_json(self, client):
        """Test CSP report endpoint with empty JSON body."""
        response = client.post(
            reverse('csp.report'),
            data='{}',
            content_type='application/json'
        )
        # Should handle empty JSON gracefully
        assert response.status_code in [200, 204, 400]

    def test_csp_report_endpoint_malformed_json(self, client):
        """Test CSP report endpoint with malformed JSON."""
        response = client.post(
            reverse('csp.report'),
            data='{bad json}',
            content_type='application/json'
        )
        # Should reject malformed JSON or handle gracefully
        assert response.status_code in [200, 204, 400]

    def test_csp_report_endpoint_missing_data(self, client):
        """Test CSP report endpoint with missing data."""
        response = client.post(
            reverse('csp.report'),
            data='',
            content_type='application/json'
        )
        # Should handle missing data gracefully
        assert response.status_code in [200, 204, 400]

    def test_metrics_endpoint(self, client):
        """Test metrics endpoint (may require auth)."""
        response = client.get(reverse('metrics'))
        # May require auth or return metrics
        assert response.status_code in [200, 401, 403]


@pytest.mark.django_db
class TestStaticPages:
    """Test static content and assets."""

    def test_static_url_pattern(self, client):
        """Test that static URL pattern is configured."""
        # Just verify the static URL doesn't 500
        response = client.get('/static/')
        # May 404 but shouldn't crash
        assert response.status_code in [200, 301, 302, 404]

    def test_media_url_pattern(self, client):
        """Test that media URL pattern is configured."""
        response = client.get('/media/')
        # May 404 but shouldn't crash
        assert response.status_code in [200, 301, 302, 404]


@pytest.mark.django_db
class TestJavaScriptHelpers:
    """Test JavaScript helper endpoints."""

    def test_js_catalog_endpoint(self, client):
        """Test JavaScript i18n catalog endpoint."""
        response = client.get('/jsi18n/en/')
        # Should return JavaScript catalog
        assert response.status_code == 200
        assert 'javascript' in response['Content-Type'].lower() or 'text' in response['Content-Type'].lower()

    def test_js_helpers_states(self, client):
        """Test states helper endpoint."""
        response = client.get('/js_helpers/states/')
        # Should return state data
        assert response.status_code in [200, 400]  # 400 if no country specified
