import pytest
from django.core.cache import caches
from django.test import override_settings

LOC_MEM_CACHE = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}


@pytest.fixture(autouse=True)
def clear_cache():
    caches['default'].clear()
    yield
    caches['default'].clear()


@pytest.mark.django_db
@override_settings(CACHES=LOC_MEM_CACHE)
def test_block_404_middleware(client):
    """
    Test that Block404Middleware triggers HTTP 429 after 30 404 requests
    and asserts Retry-After headers.
    """
    # Trigger 30 404s
    for _ in range(30):
        response = client.get('/api/v1/non_existent_endpoint_123/')
        assert response.status_code == 404

    # 31st request should be throttled
    response = client.get('/api/v1/non_existent_endpoint_123/')
    assert response.status_code == 429
    assert 'Retry-After' in response.headers
    assert response.headers['Retry-After'].isdigit()


@pytest.mark.django_db
@override_settings(CACHES=LOC_MEM_CACHE)
def test_public_stream_throttle_anonymous(client, event, room):
    """
    Test rate-limit enforcement on GET /api/v1/organizers/{event.organizer.slug}/events/{event.slug}/rooms/{room.pk}/streams/current/.
    Anonymous limit is 10/minute (public_stream scope).
    """
    url = f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/rooms/{room.pk}/streams/current/'

    # Trigger 10 requests which should not be 429 (might be 404 or 200)
    for _ in range(10):
        response = client.get(url)
        assert response.status_code != 429

    # 11th request should be throttled
    response = client.get(url)
    assert response.status_code == 429
    assert 'Retry-After' in response.headers


@pytest.mark.django_db
@override_settings(CACHES=LOC_MEM_CACHE)
def test_public_stream_throttle_authenticated(authenticated_client, event, room):
    """
    Test that authenticated users are NOT throttled by the PublicStreamThrottle
    because it inherits from AnonRateThrottle.
    """
    url = f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/rooms/{room.pk}/streams/current/'

    # Do 15 requests - authenticated users shouldn't be stopped at 10
    for _ in range(15):
        response = authenticated_client.get(url)
        assert response.status_code != 429


@pytest.mark.django_db
@override_settings(CACHES=LOC_MEM_CACHE)
def test_block_404_middleware_authenticated(authenticated_client):
    """
    Ensure Block404Middleware throttles authenticated users as well.
    """
    for _ in range(30):
        response = authenticated_client.get('/api/v1/non_existent_endpoint_auth/')
        assert response.status_code == 404

    response = authenticated_client.get('/api/v1/non_existent_endpoint_auth/')
    assert response.status_code == 429
