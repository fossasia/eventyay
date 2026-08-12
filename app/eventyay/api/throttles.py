from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, SimpleRateThrottle


class PublicStreamThrottle(AnonRateThrottle):
    """
    Stricter throttle for the ``/rooms/{id}/streams/current`` endpoint.
    The frontend polls this endpoint; the server‑side limit acts as a
    back‑stop against misbehaving or malicious clients.
    """
    scope = 'public_stream'


class PublicScheduleThrottle(AnonRateThrottle):
    """
    Throttle for schedule‑related public endpoints (e.g. ``/schedule``).
    """
    scope = 'public_schedule'


class Excessive404Throttle(SimpleRateThrottle):
    """
    Generic throttle used by the ``Block404Middleware`` to
    limit clients that generate a large number of 404 responses in a short
    period.  The ``excessive_404`` scope is defined in ``DEFAULT_THROTTLE_RATES``.
    """
    scope = 'excessive_404'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }
