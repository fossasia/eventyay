import functools
import logging
from typing import cast

import requests
from allauth.account.utils import filter_users_by_email
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.mediawiki.views import MediaWikiOAuth2Adapter
from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse

from .email import ensure_verified_email_for_user, get_verified_mediawiki_sociallogin_email

logger = logging.getLogger(__name__)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    # Override to setup User-Agent to follow Wikimedia policy
    # https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
    def get_requests_session(self):
        # The self.request was populated by BaseAdapter.
        dj_request = cast(HttpRequest, self.request)
        site_url = dj_request.build_absolute_uri('/')
        try:
            contact = settings.ADMINS[0][1]
        except (AttributeError, IndexError):
            contact = 'webmaster@eventyay.com'
        user_agent = f'eventyay/1.0 ({site_url}; {contact})'

        session = requests.Session()
        session.headers.update({'User-Agent': user_agent})
        session.request = functools.partial(session.request, timeout=app_settings.REQUESTS_TIMEOUT)
        return session

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        logger.error('Error while authorizing with %s: %s - %s', provider, error, exception)
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse('control:index')))

    def pre_social_login(self, request: HttpRequest, sociallogin) -> None:
        super().pre_social_login(request, sociallogin)
        if sociallogin.provider.id != 'mediawiki':
            return

        email = get_verified_mediawiki_sociallogin_email(sociallogin)
        if not email:
            email = self.fetch_mediawiki_profile_email(sociallogin)

        if sociallogin.is_existing:
            ensure_verified_email_for_user(sociallogin.user, email)
            return
        if not app_settings.EMAIL_AUTHENTICATION:
            return
        if not email:
            return

        users = filter_users_by_email(email, prefer_verified=True)
        if users:
            sociallogin.user = users[0]
            sociallogin._did_authenticate_by_email = email
            ensure_verified_email_for_user(users[0], email)

    def fetch_mediawiki_profile_email(self, sociallogin) -> str | None:
        token = sociallogin.token
        if not token or not token.token:
            return None

        headers = {'Authorization': f'Bearer {token.token}'}
        try:
            with self.get_requests_session() as session:
                response = session.get(
                    MediaWikiOAuth2Adapter.profile_url,
                    headers=headers,
                    timeout=app_settings.REQUESTS_TIMEOUT,
                )
                response.raise_for_status()
                profile = response.json()
        except requests.RequestException as e:
            logger.warning('Could not fetch MediaWiki profile during social login: %s', e)
            return None
        except ValueError as e:
            logger.warning('Could not decode MediaWiki profile response during social login: %s', e)
            return None

        if not isinstance(profile, dict):
            return None

        email = profile.get('email')
        if not isinstance(email, str) or not email:
            return None
        if profile.get('confirmed_email') is False:
            return None
        return email

    def can_authenticate_by_email(self, login, email):
        # Keep MediaWiki behavior aligned with global email-auth settings even when
        # per-app JSON settings contain `email_authentication: false`.
        if login.provider.id == 'mediawiki' and app_settings.EMAIL_AUTHENTICATION:
            return True
        return super().can_authenticate_by_email(login, email)
