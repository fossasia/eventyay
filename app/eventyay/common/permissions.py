import logging

from django.http import HttpRequest

logger = logging.getLogger(__name__)


def is_admin_mode_active(request: HttpRequest) -> bool:
    if request and hasattr(request.user, 'has_active_staff_session') and request.user.has_active_staff_session(request.session.session_key):
        logger.debug(
            'User %s has active staff session - granting admin access to %s',
            request.user,
            request.path
        )
        return True

    return False
