import hashlib
import time

from django.conf import settings


class SessionInvalid(Exception):  # NOQA: N818
    pass


class SessionReauthRequired(Exception):  # NOQA: N818
    pass


def get_user_agent_hash(request):
    return hashlib.sha256(request.headers['User-Agent'].encode()).hexdigest()


def assert_session_valid(request):
    """Validate the session for timeouts and User-Agent pinning.

    Behavior differences for long sessions:
    - If the feature is globally enabled and the session has the long-session flag,
      we *do not* enforce absolute/relative timeouts nor User-Agent pinning; instead
      we refresh the pinned User-Agent so that, should UA pinning later resume,
      it will be initialized to the current client value (avoiding spurious logouts).

    - If the feature is disabled globally, any per-session flag should NOT bypass
      normal checks.
    """
    is_long_session = settings.EVENTYAY_LONG_SESSIONS and request.session.get('eventyay_auth_long_session', False)

    if is_long_session:
        # Refresh pinned UA proactively during long sessions so that when UA pinning
        # resumes the value is up-to-date (avoids unexpected invalidations on toggle).
        if 'User-Agent' in request.headers:
            request.session['pinned_user_agent'] = get_user_agent_hash(request)
        request.session['eventyay_auth_last_used'] = int(time.time())
        return True

    # Short sessions: enforce absolute and relative timeouts
    last_used = request.session.get('eventyay_auth_last_used', time.time())
    if (
        time.time() - request.session.get('eventyay_auth_login_time', time.time())
        > settings.EVENTYAY_SESSION_TIMEOUT_ABSOLUTE
    ):
        request.session['eventyay_auth_login_time'] = 0
        raise SessionInvalid()
    if time.time() - last_used > settings.EVENTYAY_SESSION_TIMEOUT_RELATIVE:
        raise SessionReauthRequired()

    # Enforce User-Agent pinning for short sessions. If none exists yet, initialize
    # it to the current User-Agent to avoid immediate logout on transition from a
    # long session that did not set it previously.
    if 'User-Agent' in request.headers:
        if 'pinned_user_agent' in request.session:
            if request.session.get('pinned_user_agent') != get_user_agent_hash(request):
                raise SessionInvalid()
        else:
            request.session['pinned_user_agent'] = get_user_agent_hash(request)

    request.session['eventyay_auth_last_used'] = int(time.time())
    return True
