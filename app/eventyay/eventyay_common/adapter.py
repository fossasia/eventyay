import time
from urllib.parse import urlencode

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context
from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from pydantic import ValidationError

from eventyay.base.auth import get_auth_backends
from eventyay.common.consts import KEY_LAST_FORCE_LOGIN, KEY_LONG_SESSION, KEY_SOCIAL_KEEP_LOGGED_IN
from eventyay.helpers.cookies import set_cookie_without_samesite
from eventyay.helpers.jwt_generate import generate_sso_token
from eventyay.multidomain.middlewares import get_cookie_domain
from eventyay.plugins.socialauth.schemas.oauth2_params import OAuth2Params


class CustomAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        pretix_auth_backends = get_auth_backends()
        return settings.EVENTYAY_REGISTRATION and 'native' in pretix_auth_backends

    def get_login_redirect_url(self, request):
        # Social login → OAuth2 handoff for Talk module.
        oauth2_params = request.session.pop('oauth2_params', None)
        if oauth2_params:
            try:
                validated_oauth2_params = OAuth2Params.model_validate(oauth2_params)
            except ValidationError:
                validated_oauth2_params = None

        else:
            validated_oauth2_params = None

        if validated_oauth2_params:
            request.session.pop('socialauth_next_url', None)
            auth_url = reverse('eventyay_common:oauth2_provider.authorize')
            return f'{auth_url}?{urlencode(validated_oauth2_params.model_dump())}'

        next_url = request.session.pop('socialauth_next_url', None)
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=None):
            return next_url

        return super().get_login_redirect_url(request)

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

        response = super().post_login(
            request,
            user,
            email_verification=email_verification,
            signal_kwargs=signal_kwargs,
            email=email,
            signup=signup,
            redirect_url=redirect_url,
        )

        # JWT cookie lets the Talk sub-app verify the user without shared sessions.
        if isinstance(response, HttpResponseRedirect) and request.user.is_authenticated:
            token = generate_sso_token(request.user)
            set_cookie_without_samesite(
                request,
                response,
                'sso_token',
                token,
                max_age=settings.CSRF_COOKIE_AGE,
                domain=get_cookie_domain(request),
                path=settings.CSRF_COOKIE_PATH,
                secure=request.scheme == 'https',
                httponly=True,
            )
        return response

    def send_account_already_exists_mail(self, email: str) -> None:
        request = context.request
        ctx = {
            'signup_url': request.build_absolute_uri(reverse('account_signup')),
            'password_reset_url': request.build_absolute_uri(reverse('eventyay_common:auth.forgot')),
        }
        self.send_mail('account/email/account_already_exists', email, ctx)
