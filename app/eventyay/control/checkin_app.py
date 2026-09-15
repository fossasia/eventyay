from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

CHECKIN_APP_PRODUCTION_URL = 'https://access.eventyay.com/'


def request_hostname_for_dev_url(request):
    """Hostname from request host header, bracketed when IPv6."""
    hostname = urlparse(f'//{request.get_host()}').hostname or 'localhost'
    if ':' in hostname:
        return f'[{hostname}]'
    return hostname


def is_eventyay_checkin_app_dev() -> bool:
    """True when the check-in app should use the local Vite dev server."""
    if not (settings.VITE_DEV_MODE and getattr(settings, 'PLUGIN_DEV_MODE', False)):
        return False
    container_checkin_dir = Path('/usr/src/plugins/eventyay-checkin')
    repo_checkin_dir = settings.PROJECT_ROOT.parent / 'plugins' / 'eventyay-checkin'
    return container_checkin_dir.is_dir() or repo_checkin_dir.is_dir()


def get_eventyay_checkin_app_url(request):
    """Public URL for the eventyay Check-in web app (device/kiosk UI)."""
    if is_eventyay_checkin_app_dev():
        return f'http://{request_hostname_for_dev_url(request)}:8085/'
    return CHECKIN_APP_PRODUCTION_URL


def user_can_open_checkin_app(request):
    return request.user.has_event_permission(
        request.organizer,
        request.event,
        ('can_change_orders', 'can_checkin_orders'),
        request=request,
    )
