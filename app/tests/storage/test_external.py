from unittest.mock import MagicMock, patch

import requests
from django.conf import settings

from eventyay.storage.external import fetch_preview_data, retrieve_url


class TestRetrieveUrl:
    """Unit tests for the retrieve_url helper."""

    def test_retrieve_url_success(self):
        """Test successful HTTP GET request returning 200 response with User-Agent header."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200

        with patch('requests.get', return_value=mock_response) as mock_get:
            response = retrieve_url('https://example.com/image.png')

            assert response == mock_response
            mock_get.assert_called_once_with(
                'https://example.com/image.png',
                headers={'User-Agent': f'{settings.INSTANCE_NAME}/1.0 ({settings.SITE_URL})'},
                timeout=10,
            )

    def test_retrieve_url_non_200_status(self):
        """Test that non-200 HTTP status code returns None."""
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 404

        with patch('requests.get', return_value=mock_response):
            response = retrieve_url('https://example.com/missing.png')
            assert response is None

    def test_retrieve_url_timeout_exception(self):
        """Test that a Timeout exception is caught, logged, and returns None."""
        with (
            patch('requests.get', side_effect=requests.exceptions.Timeout('Read timeout')),
            patch('eventyay.storage.external.logger.warning') as mock_log,
        ):
            response = retrieve_url('https://example.com/timeout')
            assert response is None
            mock_log.assert_called_once_with('Failed to fetch external URL: %s', 'Timeout')

    def test_retrieve_url_connection_error(self):
        """Test that a ConnectionError exception is caught and returns None."""
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError('DNS failure')):
            response = retrieve_url('https://non-existent-domain.xyz')
            assert response is None

    def test_retrieve_url_ssl_error(self):
        """Test that an SSLError exception is caught and returns None."""
        with patch('requests.get', side_effect=requests.exceptions.SSLError('Certificate error')):
            response = retrieve_url('https://self-signed.badssl.com')
            assert response is None

    def test_retrieve_url_too_many_redirects(self):
        """Test that a TooManyRedirects exception is caught and returns None."""
        with patch('requests.get', side_effect=requests.exceptions.TooManyRedirects('Loop')):
            response = retrieve_url('https://redirect-loop.com')
            assert response is None


class TestFetchPreviewData:
    """Unit tests for fetch_preview_data error handling and fallback behavior."""

    def test_fetch_preview_data_handles_unreachable_url(self):
        """Test that fetch_preview_data returns None when retrieve_url fails."""
        with patch('eventyay.storage.external.retrieve_url', return_value=None):
            result = fetch_preview_data('https://unreachable.example.com', event=None)
            assert result is None

    def test_fetch_preview_data_html_with_broken_image_preview(self):
        """Test that preview extraction succeeds even if the og:image URL is unreachable."""
        html_content = b"""
        <html>
        <head>
            <meta property="og:title" content="Test Event">
            <meta property="og:description" content="An awesome event">
            <meta property="og:image" content="https://example.com/broken_image.png">
        </head>
        <body></body>
        </html>
        """
        mock_page_response = MagicMock(spec=requests.Response)
        mock_page_response.status_code = 200
        mock_page_response.headers = {'Content-Type': 'text/html'}
        mock_page_response.content = html_content

        def mock_retrieve_side_effect(url):
            if url == 'https://example.com/page':
                return mock_page_response
            return None  # Image fetch fails

        with patch('eventyay.storage.external.retrieve_url', side_effect=mock_retrieve_side_effect):
            result = fetch_preview_data('https://example.com/page', event=None)

            assert result is not None
            assert result['title'] == 'Test Event'
            assert result['description'] == 'An awesome event'
            assert 'image' not in result
