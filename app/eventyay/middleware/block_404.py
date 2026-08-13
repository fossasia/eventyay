import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import caches
from django.http import HttpResponse
from eventyay.helpers.http import get_client_ip

logger = logging.getLogger(__name__)


class Block404Middleware(MiddlewareMixin):
    """
    Middleware that tracks the number of 404 responses per client IP and applies a throttle
    when the limit is breached.
    """
    # Thresholds – can be overridden via Django settings if required.
    MAX_404_PER_MINUTE = 30
    CACHE_ALIAS = 'default'  # Use the primary cache (Redis)

    def process_request(self, request):
        ip = get_client_ip(request)
        cache = caches[self.CACHE_ALIAS]
        key = f'404_counter:{ip}'
        try:
            count = cache.get(key, 0)
        except Exception:
            count = 0
            
        if count and int(count) > self.MAX_404_PER_MINUTE:
            return HttpResponse(
                content='Too many 404 responses – request throttled.',
                status=429,
                headers={'Retry-After': '60'}
            )
        return None

    def process_response(self, request, response):
        # Only act on 404 responses.
        if response.status_code != 404:
            return response

        ip = get_client_ip(request)
        cache = caches[self.CACHE_ALIAS]
        key = f'404_counter:{ip}'
        
        try:
            # Atomically increment counter, setting initial value if it doesn't exist
            cache.add(key, 0, timeout=60)
            count = cache.incr(key)
        except ValueError:
            # DummyCache raises ValueError on incr if key not found (but add doesn't actually store in DummyCache)
            return response
        except Exception:
            # Fail open on other cache errors (Redis down, etc.)
            return response

        if count > self.MAX_404_PER_MINUTE:
            return HttpResponse(
                content='Too many 404 responses – request throttled.',
                status=429,
                headers={'Retry-After': '60'}
            )
        return response

