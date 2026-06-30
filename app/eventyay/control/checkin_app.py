import os
from urllib.parse import urlparse

CHECKIN_APP_PRODUCTION_URL = 'https://access.eventyay.com/'


def _request_hostname_for_dev_url(request):
    """Hostname from request host header, bracketed when IPv6."""
    hostname = urlparse(f'//{request.get_host()}').hostname or 'localhost'
    if ':' in hostname:
        return f'[{hostname}]'
    return hostname


def get_eventyay_checkin_app_url(request):
    """Public URL for the eventyay Check-in web app (device/kiosk UI)."""
    if os.environ.get('EVY_NPM_DEV') == '1':
        return f'http://{_request_hostname_for_dev_url(request)}:8085/'
    return CHECKIN_APP_PRODUCTION_URL


def user_can_open_checkin_app(request):
    return request.user.has_event_permission(
        request.organizer,
        request.event,
        ('can_change_orders', 'can_checkin_orders'),
        request=request,
    )
