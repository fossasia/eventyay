from django.core.cache import cache
from django.db import connection
from rest_framework.response import Response
from rest_framework.views import APIView


class CheckinHealthView(APIView):
    """Health check for the dedicated check-in worker pool.

    Returns HTTP 200 when the database and cache backends are reachable,
    or HTTP 503 with error details otherwise. This endpoint is intended
    to be polled by a load-balancer or monitoring system independently
    of the general application health check.
    """

    permission_classes = []
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        try:
            connection.ensure_connection()
            cache.get("checkin_health_check")
            return Response({"status": "ok"})
        except Exception as e:
            return Response(
                {"status": "error", "detail": str(e)},
                status=503,
            )
