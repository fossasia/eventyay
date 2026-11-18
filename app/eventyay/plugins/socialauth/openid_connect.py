import logging
from typing import Any

import requests
from allauth.core.exceptions import ImmediateHttpResponse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.operational_logging import OUTCOME_FAILURE, log_event


logger = logging.getLogger(__name__)


def patch_openid_connect() -> None:
    """
    Safely wrap allauth's OpenIDConnectOAuth2Adapter to handle network, connection,
    and decoding errors gracefully instead of raising unhandled 500 server errors.
    """
    try:
        from allauth.socialaccount.providers.openid_connect.views import OpenIDConnectOAuth2Adapter
    except ImportError:
        return

    if getattr(OpenIDConnectOAuth2Adapter, '_eventyay_patched', False):
        return

    orig_openid_config = OpenIDConnectOAuth2Adapter.openid_config

    @property
    def safe_openid_config(self: OpenIDConnectOAuth2Adapter) -> dict[str, Any]:
        try:
            return orig_openid_config.__get__(self, OpenIDConnectOAuth2Adapter)
        except (requests.RequestException, ValueError, KeyError) as e:
            provider = self.get_provider()
            server_url = getattr(provider, 'server_url', 'unknown')
            logger.error('Failed to retrieve OpenID configuration from %s: %s', server_url, e)
            messages.error(
                self.request,
                _('Unable to connect to the identity provider. Please verify the server URL or try again later.'),
            )
            log_event('core', 'auth.login', OUTCOME_FAILURE, error_code='oidc_server_unreachable')
            raise ImmediateHttpResponse(HttpResponseRedirect(reverse('auth.login'))) from e

    orig_fetch_user_info = OpenIDConnectOAuth2Adapter._fetch_user_info

    def safe_fetch_user_info(self: OpenIDConnectOAuth2Adapter, access_token: str) -> dict[str, Any]:
        try:
            return orig_fetch_user_info(self, access_token)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.error('Failed to fetch userinfo from OpenID Connect provider: %s', e)
            messages.error(
                self.request,
                _('Failed to retrieve user information from the identity provider. Please try again.'),
            )
            log_event('core', 'auth.login', OUTCOME_FAILURE, error_code='oidc_userinfo_failed')
            raise ImmediateHttpResponse(HttpResponseRedirect(reverse('auth.login'))) from e

    OpenIDConnectOAuth2Adapter.openid_config = safe_openid_config
    OpenIDConnectOAuth2Adapter._fetch_user_info = safe_fetch_user_info
    OpenIDConnectOAuth2Adapter._eventyay_patched = True
