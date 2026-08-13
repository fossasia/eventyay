import logging

from django.core.cache import caches
from django.http import HttpResponse

from eventyay.helpers.http import get_client_ip

logger = logging.getLogger(__name__)


class Block404Middleware:
    """
    Middleware that tracks the number of 404 responses per client IP and applies a throttle
    when the limit is breached.
    """
    MAX_404_PER_MINUTE = 30
    CACHE_ALIAS = 'default'
    RETRY_AFTER_SECONDS = '60'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        cache = caches[self.CACHE_ALIAS]
        key = f'404_counter:{ip}'

        try:
            count = int(cache.get(key, 0))
        except Exception:
            count = 0

        if count >= self.MAX_404_PER_MINUTE:
            return self._too_many_requests_response()

        response = self.get_response(request)

        if response.status_code != 404:
            return response

        try:
            count = self._increment(cache, key)
        except Exception:
            logger.exception('Failed to increment 404 counter for IP %s', ip)
            return response

        if count > self.MAX_404_PER_MINUTE:
            return self._too_many_requests_response()
        return response

    @classmethod
    def _increment(cls, cache, key):
        try:
            return cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=60)
            return 1

    @classmethod
    def _too_many_requests_response(cls):
        return HttpResponse(
            content='Too many 404 responses – request throttled.',
            status=429,
            headers={'Retry-After': cls.RETRY_AFTER_SECONDS},
        )
