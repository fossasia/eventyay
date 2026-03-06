import time

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.http import HttpRequest

from eventyay.common.consts import KEY_LAST_FORCE_LOGIN, KEY_LONG_SESSION


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return settings.EVENTYAY_REGISTRATION and super().is_open_for_signup(request)

    def post_login(
        self,
        request: HttpRequest,
        user,
        *,
        email_verification,
        signal_kwargs,
        email,
        signup,
        redirect_url,
    ):
        # Replicate the behavior of previous `eventyay_common.views.auth.register()` view.
        request.session[KEY_LAST_FORCE_LOGIN] = int(time.time())
        request.session[KEY_LONG_SESSION] = (
            settings.EVENTYAY_LONG_SESSIONS and not request.session.get_expire_at_browser_close()
        )
        return super().post_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )
