import logging
from typing import Any
from urllib.parse import urlencode

import stripe
from django.conf import settings as django_settings
from django.core import signing
from django.utils.translation import gettext_lazy as _

from eventyay.base.settings import GlobalSettingsObject


logger = logging.getLogger(__name__)

STRIPE_CONNECT_OAUTH_STATE_SALT = 'eventyay.stripe_connect.oauth'
STRIPE_CONNECT_OAUTH_STATE_MAX_AGE = 600
STRIPE_CONNECT_AUTHORIZE_URL = 'https://connect.stripe.com/oauth/authorize'


def get_stripe_connect_credentials(event=None) -> dict[str, Any]:
    """Retrieve platform Stripe Connect credentials.

    For test-mode events, strictly retrieves test-mode credentials and avoids
    falling back to live keys to prevent unintentional charges against live resources.

    Args:
        event: Optional Event instance to check testmode configuration.

    Returns:
        A dictionary containing client_id, secret_key, publishable_key, is_configured flag,
        and testmode status.
    """
    gs = GlobalSettingsObject()
    testmode = bool(event and getattr(event, 'testmode', False))

    client_id = (
        gs.settings.get('payment_stripe_connect_client_id')
        or getattr(django_settings, 'STRIPE_CONNECT_CLIENT_ID', '')
    )

    if testmode:
        secret_key = (
            gs.settings.get('payment_stripe_connect_test_secret_key')
            or getattr(django_settings, 'STRIPE_CONNECT_TEST_SECRET_KEY', '')
        )
        publishable_key = (
            gs.settings.get('payment_stripe_connect_test_publishable_key')
            or getattr(django_settings, 'STRIPE_CONNECT_TEST_PUBLISHABLE_KEY', '')
        )
    else:
        secret_key = (
            gs.settings.get('payment_stripe_connect_secret_key')
            or getattr(django_settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        )
        publishable_key = (
            gs.settings.get('payment_stripe_connect_publishable_key')
            or getattr(django_settings, 'STRIPE_CONNECT_PUBLISHABLE_KEY', '')
        )

    return {
        'client_id': client_id or '',
        'secret_key': secret_key or '',
        'publishable_key': publishable_key or '',
        'is_configured': bool(client_id and secret_key),
        'testmode': testmode,
    }


def get_event_stripe_publishable_key(event) -> str:
    """Resolve the appropriate Stripe publishable key for an event.

    For Stripe Connect accounts in test mode, strictly ensures a test publishable key
    (starting with 'pk_test_') is returned and prevents pairing a test secret key
    with a live publishable key stored from OAuth.

    Args:
        event: The Event instance.

    Returns:
        The resolved Stripe publishable key string, or empty string.
    """
    if not event:
        return ''

    connect_user_id = event.settings.get('payment_stripe_connect_user_id')
    if connect_user_id:
        creds = get_stripe_connect_credentials(event)
        if getattr(event, 'testmode', False):
            platform_test_pk = creds.get('publishable_key') or ''
            stored_pk = event.settings.get('payment_stripe_connect_publishable_key') or ''
            if platform_test_pk and platform_test_pk.startswith('pk_test_'):
                return platform_test_pk
            if stored_pk and stored_pk.startswith('pk_test_'):
                return stored_pk
            return ''
        return (
            event.settings.get('payment_stripe_connect_publishable_key')
            or creds.get('publishable_key')
            or ''
        )
    return event.settings.get('payment_stripe_publishable_key') or ''


def build_stripe_oauth_state(*, event_id: int, user_id: int, next_url: str = '', nonce: str = '') -> str:
    """Build a cryptographically signed OAuth state token.

    Args:
        event_id: Primary key of the event being configured.
        user_id: Primary key of the user initiating the connection.
        next_url: Post-authorization redirect target URL.
        nonce: Cryptographic random nonce for browser session binding.

    Returns:
        HMAC-signed state token string.
    """
    payload = {
        'event_id': event_id,
        'user_id': user_id,
        'next_url': next_url,
        'nonce': nonce,
    }
    return signing.dumps(payload, salt=STRIPE_CONNECT_OAUTH_STATE_SALT)


def load_stripe_oauth_state(state: str) -> dict[str, Any]:
    """Validate and decode a signed OAuth state token.

    Args:
        state: HMAC-signed state token received from the OAuth callback.

    Returns:
        Decoded payload dictionary.

    Raises:
        BadSignature: If the state token has been tampered with or is invalid.
        SignatureExpired: If the state token has exceeded the maximum age.
    """
    return signing.loads(
        state,
        salt=STRIPE_CONNECT_OAUTH_STATE_SALT,
        max_age=STRIPE_CONNECT_OAUTH_STATE_MAX_AGE,
    )


def build_stripe_authorize_url(*, redirect_uri: str, state: str, event=None) -> str:
    """Construct the Stripe Connect OAuth authorization URL.

    Args:
        redirect_uri: Absolute callback URL configured for Stripe redirects.
        state: Signed state parameter to prevent CSRF.
        event: Optional Event instance for credential resolution.

    Returns:
        Complete Stripe OAuth authorize URL.

    Raises:
        ValueError: If platform Client ID is not configured.
    """
    creds = get_stripe_connect_credentials(event)
    client_id = creds.get('client_id')
    if not client_id:
        raise ValueError(_('Stripe Connect Client ID is not configured on this platform.'))

    params = {
        'response_type': 'code',
        'client_id': client_id,
        'scope': 'read_write',
        'redirect_uri': redirect_uri,
        'state': state,
    }
    return f'{STRIPE_CONNECT_AUTHORIZE_URL}?{urlencode(params)}'


def exchange_stripe_authorization_code(*, code: str, event=None) -> dict[str, Any]:
    """Exchange authorization code for access credentials via stripe.OAuth.token.

    Args:
        code: Authorization code returned by Stripe in the callback.
        event: Optional Event instance for credential resolution.

    Returns:
        Stripe OAuth token response dictionary containing stripe_user_id and keys.

    Raises:
        ValueError: If platform Stripe secret key is missing.
        stripe.error.StripeError: If the token exchange fails on the Stripe API.
    """
    creds = get_stripe_connect_credentials(event)
    secret_key = creds.get('secret_key')
    if not secret_key:
        raise ValueError(_('Stripe Connect secret key is not configured on this platform.'))

    return stripe.OAuth.token(
        grant_type='authorization_code',
        code=code,
        api_key=secret_key,
    )


def get_stripe_account_display_name(stripe_user_id: str, event=None) -> str:
    """Attempt to retrieve a human-readable display name for the connected Stripe account.

    Args:
        stripe_user_id: Connected account identifier (e.g. acct_...).
        event: Optional Event instance for credential resolution.

    Returns:
        Account business profile name, dashboard display name, email, or account ID fallback.
    """
    creds = get_stripe_connect_credentials(event)
    secret_key = creds.get('secret_key')
    if not secret_key or not stripe_user_id:
        return stripe_user_id

    try:
        acct = stripe.Account.retrieve(stripe_user_id, api_key=secret_key)
        biz_profile = getattr(acct, 'business_profile', None) or {}
        if isinstance(biz_profile, dict) and biz_profile.get('name'):
            return biz_profile['name']
        if hasattr(biz_profile, 'name') and biz_profile.name:
            return biz_profile.name

        settings_obj = getattr(acct, 'settings', None) or {}
        dashboard = (
            getattr(settings_obj, 'dashboard', None)
            if hasattr(settings_obj, 'dashboard')
            else (settings_obj.get('dashboard') if isinstance(settings_obj, dict) else None)
        )
        if dashboard:
            if hasattr(dashboard, 'display_name'):
                d_name = dashboard.display_name
            elif isinstance(dashboard, dict):
                d_name = dashboard.get('display_name')
            else:
                d_name = None
            if d_name:
                return d_name

        email = getattr(acct, 'email', None)
        if email:
            return email
    except stripe.error.StripeError as exc:
        logger.warning('Could not retrieve display name for Stripe account %s: %s', stripe_user_id, exc)

    return stripe_user_id


def deauthorize_stripe_account(*, stripe_user_id: str, event=None) -> None:
    """Revoke access to the connected Stripe account.

    Args:
        stripe_user_id: Connected account identifier to deauthorize.
        event: Optional Event instance for credential resolution.

    Raises:
        ValueError: If platform credentials or stripe_user_id are missing.
        stripe.error.StripeError: If Stripe API deauthorization fails.
    """
    creds = get_stripe_connect_credentials(event)
    secret_key = creds.get('secret_key')
    client_id = creds.get('client_id')
    if not secret_key or not client_id or not stripe_user_id:
        raise ValueError(_('Stripe Connect platform credentials or account ID are missing.'))

    secret_is_mock = secret_key.startswith('sk_test_mock')
    client_is_mock = client_id.startswith('ca_test_mock')
    if secret_is_mock and client_is_mock:
        logger.info('Mock Stripe credentials detected; skipping remote deauthorization for %s', stripe_user_id)
        return
    if secret_is_mock or client_is_mock:
        raise ValueError(_('Stripe Connect mock credentials must be configured together.'))

    stripe.OAuth.deauthorize(
        client_id=client_id,
        stripe_user_id=stripe_user_id,
        api_key=secret_key,
    )
