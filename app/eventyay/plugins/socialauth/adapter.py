import functools
import logging
from typing import cast

import requests
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject

logger = logging.getLogger(__name__)


def require_provider_enabled(request, provider):
    gs = GlobalSettingsObject()
    login_providers = gs.settings.get('login_providers', as_type=dict) or {}
    cfg = login_providers.get(provider)
    if (
        not isinstance(cfg, dict)
        or not cfg.get('state')
        or not cfg.get('client_id')
        or not cfg.get('secret')
    ):
        logger.warning('Social login attempt for unavailable provider: %s', provider)
        messages.error(request, _('This login method is not available.'))
        raise ImmediateHttpResponse(
            HttpResponseRedirect(reverse('eventyay_common:auth.login'))
        )


def sync_wikimedia_username(user, sociallogin):
    if sociallogin.account.provider != 'mediawiki':
        return
    extra_data = sociallogin.account.extra_data or {}
    wikimedia_username = extra_data.get('username', extra_data.get('realname', ''))
    if wikimedia_username and user.wikimedia_username != wikimedia_username:
        user.wikimedia_username = wikimedia_username
        user.save(update_fields=['wikimedia_username'])


def lookup_by_wikimedia_username(sociallogin) -> User | None:
    """Fallback lookup when the MediaWiki OAuth consumer does not return an email."""
    if sociallogin.account.provider != 'mediawiki':
        return None
    extra_data = sociallogin.account.extra_data or {}
    wikimedia_username = extra_data.get('username', '')
    if not wikimedia_username:
        return None
    rows = list(User.objects.filter(wikimedia_username=wikimedia_username)[:2])
    if len(rows) == 0:
        return None
    if len(rows) > 1:
        logger.warning(
            'Multiple users share wikimedia_username=%s; skipping fallback lookup',
            wikimedia_username,
        )
        return None
    return rows[0]


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    # https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
    def get_requests_session(self):
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

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        sync_wikimedia_username(user, sociallogin)
        return user

    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)
        require_provider_enabled(request, sociallogin.account.provider)

        # Email lookup failed — MediaWiki consumer likely lacks email permission.
        # Fall back to matching by wikimedia_username set on the User profile.
        if not sociallogin.is_existing:
            user = lookup_by_wikimedia_username(sociallogin)
            if user is not None:
                sociallogin.user = user
                # _did_authenticate_by_email is already None here: _lookup_by_email
                # only sets it when it finds a match, which it didn't (we're in the
                # not-existing branch).  No password-wipe risk.

        if sociallogin.is_existing:
            sync_wikimedia_username(sociallogin.user, sociallogin)
