import hashlib
import time

from django.conf import settings
from django.http import HttpRequest

from eventyay.common.consts import KEY_LAST_FORCE_LOGIN, KEY_LAST_LOGIN_CHECK, KEY_LONG_SESSION, KEY_PINNED_USER_AGENT


class SessionInvalid(Exception):  # NOQA: N818
    pass


class SessionReauthRequired(Exception):  # NOQA: N818
    pass


def get_user_agent_hash(request: HttpRequest) -> str:
    return hashlib.sha256(request.headers['User-Agent'].encode()).hexdigest()


# Raises:
# - SessionInvalid: when the session is invalid and should be cleared.
# - SessionReauthRequired: when the session is still valid but the user should be asked to re-authenticate.
def assert_session_valid(request: HttpRequest) -> bool:
    now = time.time()

    if not (settings.EVENTYAY_LONG_SESSIONS and request.session.get(KEY_LONG_SESSION, False)):
        last_login_check = request.session.get(KEY_LAST_LOGIN_CHECK, now)
        if (
            now - request.session.get(KEY_LAST_FORCE_LOGIN, now)
            > settings.EVENTYAY_SESSION_TIMEOUT_ABSOLUTE
        ):
            request.session[KEY_LAST_FORCE_LOGIN] = 0
            raise SessionInvalid()
        if now - last_login_check > settings.EVENTYAY_SESSION_TIMEOUT_RELATIVE:
            raise SessionReauthRequired()

    if 'User-Agent' in request.headers:
        if KEY_PINNED_USER_AGENT in request.session:
            if request.session.get(KEY_PINNED_USER_AGENT) != get_user_agent_hash(request):
                if settings.EVENTYAY_LONG_SESSIONS and request.session.get(KEY_LONG_SESSION, False):
                    # Long session: re-pin UA instead of invalidating (UA can change with device/viewport).
                    request.session[KEY_PINNED_USER_AGENT] = get_user_agent_hash(request)
                else:
                    raise SessionInvalid()
        else:
            request.session[KEY_PINNED_USER_AGENT] = get_user_agent_hash(request)

    request.session[KEY_LAST_LOGIN_CHECK] = int(time.time())
    return True
