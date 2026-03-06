import random
import socket

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect, StreamingHttpResponse


SMTP_REACHABLE_CACHE_TTL_BASE = 300
SMTP_REACHABLE_CACHE_TTL_JITTER = 30


class ChunkBasedFileResponse(StreamingHttpResponse):
    block_size = 4096

    def __init__(self, streaming_content=(), *args, **kwargs):
        filelike = streaming_content
        streaming_content = streaming_content.chunks(self.block_size)
        super().__init__(streaming_content, *args, **kwargs)
        self['Content-Length'] = filelike.size


def get_client_ip(request):
    ip = request.META.get('REMOTE_ADDR')
    if settings.TRUST_X_FORWARDED_FOR:
        x_forwarded_for = request.headers.get('x-forwarded-for')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
    return ip


def redirect_to_url(to, permanent=False):
    redirect_class = HttpResponsePermanentRedirect if permanent else HttpResponseRedirect
    return redirect_class(to)


def smtp_reachable(host: str | None, port: int | None, timeout: int | float | None = None) -> bool:
    """Check SMTP TCP reachability and cache the result for ~5 minutes with jitter."""
    if not host or not port:
        return False

    port_number = int(port)
    connect_timeout = timeout if timeout is not None else 5
    cache_key = f'smtp_reachable:{host}:{port_number}'
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        return cached_value

    try:
        with socket.create_connection((host, port_number), connect_timeout):
            reachable = True
    except (OSError, TypeError, ValueError):
        reachable = False

    cache_ttl = SMTP_REACHABLE_CACHE_TTL_BASE + random.randint(
        -SMTP_REACHABLE_CACHE_TTL_JITTER, SMTP_REACHABLE_CACHE_TTL_JITTER
    )
    cache.set(cache_key, reachable, timeout=cache_ttl)
    return reachable
