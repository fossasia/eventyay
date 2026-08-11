import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import caches
from django.http import HttpResponse
from eventyay.api.throttles import Excessive404Throttle

logger = logging.getLogger(__name__)


class Block404Middleware(MiddlewareMixin):
    """
    Middleware that tracks the number of 404 responses per client IP and applies a throttle
    when the limit is breached.
    """
    # Thresholds – can be overridden via Django settings if required.
    MAX_404_PER_MINUTE = 30
    CACHE_ALIAS = 'default'  # Use the primary cache (Redis)

    def process_response(self, request, response):
        # Only act on 404 responses.
        if response.status_code != 404:
            return response

        ip = self._get_client_ip(request)
        cache = caches[self.CACHE_ALIAS]
        key = f'404_counter:{ip}'
        
        # Atomically increment counter, setting initial value if it doesn't exist
        cache.add(key, 0, timeout=60)
        count = cache.incr(key)

        if count > self.MAX_404_PER_MINUTE:
            # Apply the custom throttling class to produce a 429 with Retry-After.
            throttle = Excessive404Throttle()
            if not throttle.allow_request(request, view=None):
                # throttle.wait() returns the remaining wait time in seconds.
                retry_after = int(throttle.wait())
                return HttpResponse(
                    content='Too many 404 responses – request throttled.',
                    status=429,
                    headers={'Retry-After': str(retry_after)}
                )
        return response

    def _get_client_ip(self, request):
        # Respect X-Forwarded-For when behind a proxy.
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
