import time
from urllib.parse import urlencode

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.utils import get_request_param
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from eventyay.base.auth import SPAM_ACCOUNT_ERROR, get_auth_backends
from eventyay.common.consts import KEY_LAST_FORCE_LOGIN, KEY_LONG_SESSION, KEY_SOCIAL_KEEP_LOGGED_IN
from eventyay.common.redirects import safe_redirect_url


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        pretix_auth_backends = get_auth_backends()
        return settings.EVENTYAY_REGISTRATION and 'native' in pretix_auth_backends

    def get_email_confirmation_url(self, request: HttpRequest | None, emailconfirmation) -> str:
        """Return to login with the validated destination after email verification."""
        url = super().get_email_confirmation_url(request, emailconfirmation)
        if request is None:
            return url
        target = get_request_param(request, 'next')
        if not target:
            return url
        login_url = reverse('auth.login') + '?' + urlencode({'next': safe_redirect_url(request, target)})
        separator = '&' if '?' in url else '?'
        return url + separator + urlencode({'next': login_url})

    def pre_login(
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
        # Reject login for accounts marked as spam.
        if user.is_spam:
            messages.error(request, SPAM_ACCOUNT_ERROR)
            raise ImmediateHttpResponse(
                HttpResponseRedirect(reverse('auth.login'))
            )
        return super().pre_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )

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
        request.session[KEY_LAST_FORCE_LOGIN] = int(time.time())
        social_keep = request.session.pop(KEY_SOCIAL_KEEP_LOGGED_IN, False)
        keep_logged_in = settings.EVENTYAY_LONG_SESSIONS and (
            bool(request.POST.get('keep_logged_in')) or bool(social_keep)
        )
        request.session[KEY_LONG_SESSION] = keep_logged_in

        return super().post_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )

    def send_account_already_exists_mail(self, email: str) -> None:
        request = context.request
        ctx = {
            'signup_url': request.build_absolute_uri(reverse('account_signup')),
            'password_reset_url': request.build_absolute_uri(reverse('eventyay_common:auth.forgot')),
        }
        self.send_mail('account/email/account_already_exists', email, ctx)
