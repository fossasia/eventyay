from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class EventyayAnonRateThrottle(AnonRateThrottle):
    """
    Opt-in throttle for anonymous clients on specific high-traffic endpoints.
    Do not add to DEFAULT_THROTTLE_CLASSES — IP-based keys break behind NAT.
    """
    def get_cache_key(self, request, view):
        if request.user.is_authenticated or request.auth:
            return None  # Only throttle truly anonymous users
        return super().get_cache_key(request, view)


class EventyayUserRateThrottle(UserRateThrottle):
    """
    Limits the rate of API calls for authenticated clients.
    Keys on user PK, or token PK if using API tokens (TeamAPIToken / Device),
    so shared-NAT users are not grouped into the same bucket.
    """
    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        elif request.auth:
            # Synthetic authenticated principal (TeamAPIToken or Device)
            ident = f"{type(request.auth).__name__}_{request.auth.pk}"
        else:
            return None  # Fall back to EventyayAnonRateThrottle

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }


class PublicStreamThrottle(EventyayAnonRateThrottle):
    """
    Stricter throttle (10/min) for anonymous clients on the
    ``/rooms/{id}/streams/current`` and ``/rooms/{id}/streams/next`` endpoints.
    The frontend polls these endpoints; this acts as a back-stop against
    misbehaving or malicious anonymous clients.

    Authenticated clients are covered by the EventyayUserRateThrottle that
    is always listed alongside this class on the stream actions.
    """
    scope = 'public_stream'


class PublicScheduleThrottle(EventyayAnonRateThrottle):
    """
    Throttle (30/min) for anonymous clients on schedule-related public endpoints
    (ScheduleViewSet, TalkSlotViewSet).  Authenticated clients are covered by
    EventyayUserRateThrottle listed alongside this class on those viewsets.
    """
    scope = 'public_schedule'
