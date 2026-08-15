import logging

from django.core.cache import caches
from django.http import HttpResponse

from eventyay.helpers.http import get_client_ip

logger = logging.getLogger(__name__)

# Only guard API paths — HTML pages, static files, and admin URLs are excluded
# to avoid blocking legitimate browsers under shared NAT or misconfigured proxies.
_API_PATH_PREFIX = '/api/'


class Block404Middleware:
    """
    Middleware that tracks the number of 404 responses *on API paths* per client
    IP (or user id for authenticated requests) and returns 429 Too Many Requests
    once the limit is breached.

    Scoped to ``/api/`` paths only so that normal browser navigation, static-file
    misses, and CMS 404s never trigger the block.
    """
    MAX_404_PER_MINUTE = 30
    CACHE_ALIAS = 'default'
    RETRY_AFTER_SECONDS = '60'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only guard API paths
        if not request.path.startswith(_API_PATH_PREFIX):
            return self.get_response(request)

        key = self._cache_key(request)
        cache = caches[self.CACHE_ALIAS]

        try:
            count = int(cache.get(key) or 0)
        except (ValueError, TypeError):
            count = 0

        if count >= self.MAX_404_PER_MINUTE:
            return self._too_many_requests_response()

        response = self.get_response(request)

        if response.status_code != 404:
            return response

        try:
            count = self._increment(cache, key)
        except Exception:
            logger.exception('Failed to increment 404 counter for key %s', key)
            return response

        if count > self.MAX_404_PER_MINUTE:
            return self._too_many_requests_response()
        return response

    @staticmethod
    def _cache_key(request):
        """
        Key authenticated requests by user / token identity so a single bad
        client behind shared NAT does not block other users at the same IP.
        """
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            return f'404_counter:user:{user.pk}'
        auth = getattr(request, 'auth', None)
        if auth is not None:
            return f'404_counter:token:{type(auth).__name__}_{auth.pk}'
        ip = get_client_ip(request)
        return f'404_counter:ip:{ip}'

    @classmethod
    def _increment(cls, cache, key):
        try:
            return cache.incr(key)
        except ValueError:
            # Key does not exist yet — initialise to 1 with a 60 s TTL.
            cache.set(key, 1, timeout=60)
            return 1

    @classmethod
    def _too_many_requests_response(cls):
        return HttpResponse(
            content='Too many 404 responses – request throttled.',
            status=429,
            headers={'Retry-After': cls.RETRY_AFTER_SECONDS},
        )
