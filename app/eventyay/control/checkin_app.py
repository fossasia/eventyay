import os

CHECKIN_APP_PRODUCTION_URL = 'https://access.eventyay.com/'


def get_eventyay_checkin_app_url(request):
    """Public URL for the eventyay Check-in web app (device/kiosk UI)."""
    if os.environ.get('EVY_NPM_DEV') == '1':
        host = request.get_host().split(':')[0]
        return f'http://{host}:8085/'
    return CHECKIN_APP_PRODUCTION_URL


def user_can_open_checkin_app(request):
    return request.user.has_event_permission(
        request.organizer,
        request.event,
        ('can_change_orders', 'can_checkin_orders'),
        request=request,
    )
