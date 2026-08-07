from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class CheckinEndpointThrottle(UserRateThrottle):
    """No rate limiting for authenticated check-in devices.

    Applied to check-in and badge-printing endpoints to ensure
    they are never throttled during high-traffic events.
    The ``checkin`` scope is configured with ``rate = None``
    in ``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``.
    """

    scope = "checkin"


class PublicBrowsingThrottle(AnonRateThrottle):
    """Strict rate limit for anonymous public browsing.

    Reduces the volume of low-priority anonymous requests
    (schedule pages, speaker listings) so that they are less
    likely to saturate the shared worker pool.
    """

    scope = "public_browsing"
