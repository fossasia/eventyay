"""
Tests for health and status endpoints.
"""
import pytest
from django.db import DatabaseError
from django.urls import reverse
from redis.exceptions import ConnectionError as RedisConnectionError

from eventyay.base.views.health import check_dependencies


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

    def test_dependency_probe_does_not_log_health_alerts(self, mocker):
        """Dashboard probes return failure details without emitting endpoint alerts."""
        mocker.patch('eventyay.base.models.User.objects.exists', side_effect=DatabaseError('Unavailable'))
        alert = mocker.patch('eventyay.base.views.health.logger.error')
        assert check_dependencies() == 'db_unavailable'
        alert.assert_not_called()

    @pytest.mark.parametrize('has_redis', (False, True))
    @pytest.mark.parametrize('scheme', ('redis', 'rediss'))
    @pytest.mark.parametrize('broker_available', (False, True))
    def test_healthcheck_probes_actual_broker(self, client, settings, mocker, has_redis, scheme, broker_available):
        """A healthy cache must not hide a failed broker at a different Redis endpoint."""
        settings.HAS_REDIS = has_redis
        settings.CELERY_BROKER_URL = f'{scheme}://broker.example.test:6380/8'
        cache_redis = mocker.patch('django_redis.get_redis_connection').return_value
        cache_redis.exists.return_value = True
        connect = mocker.patch('redis.Redis.from_url')
        broker = connect.return_value.__enter__.return_value
        if not broker_available:
            broker.ping.side_effect = RedisConnectionError('Broker unavailable')
        response = client.get(reverse('healthcheck'))
        assert response.status_code == (200 if broker_available else 503)
        assert response.content == (b'' if broker_available else b'Queue not available.')
        connect.assert_called_once_with(settings.CELERY_BROKER_URL, socket_connect_timeout=2, socket_timeout=2)
        broker.ping.assert_called_once_with()
        connect.return_value.__exit__.assert_called_once()
        cache_redis.ping.assert_not_called()

    def test_dependency_probe_skips_non_redis_broker(self, settings, mocker):
        """Memory-backed development brokers do not need a Redis connection."""
        settings.HAS_REDIS = False
        settings.CELERY_BROKER_URL = 'memory://'
        connect = mocker.patch('redis.Redis.from_url')
        assert check_dependencies() is None
        connect.assert_not_called()
