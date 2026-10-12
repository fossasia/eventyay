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
    """
    Retrieve platform Stripe Connect credentials based on global settings
    and testmode configuration.
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
            or gs.settings.get('payment_stripe_connect_secret_key')
            or getattr(django_settings, 'STRIPE_CONNECT_TEST_SECRET_KEY', '')
            or getattr(django_settings, 'STRIPE_CONNECT_SECRET_KEY', '')
        )
        publishable_key = (
            gs.settings.get('payment_stripe_connect_test_publishable_key')
            or gs.settings.get('payment_stripe_connect_publishable_key')
            or getattr(django_settings, 'STRIPE_CONNECT_TEST_PUBLISHABLE_KEY', '')
            or getattr(django_settings, 'STRIPE_CONNECT_PUBLISHABLE_KEY', '')
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
    }


def build_stripe_oauth_state(*, event_id: int, user_id: int, next_url: str = '') -> str:
    """
    Build a cryptographically signed OAuth state token containing event ID,
    user ID, and redirect target.
    """
    payload = {
        'event_id': event_id,
        'user_id': user_id,
        'next_url': next_url,
    }
    return signing.dumps(payload, salt=STRIPE_CONNECT_OAUTH_STATE_SALT)


def load_stripe_oauth_state(state: str) -> dict[str, Any]:
    """
    Validate and decode a signed OAuth state token, enforcing expiration.
    """
    return signing.loads(
        state,
        salt=STRIPE_CONNECT_OAUTH_STATE_SALT,
        max_age=STRIPE_CONNECT_OAUTH_STATE_MAX_AGE,
    )


def build_stripe_authorize_url(*, redirect_uri: str, state: str, event=None) -> str:
    """
    Construct the Stripe Connect OAuth authorization URL.
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
    """
    Exchange authorization code for access credentials via stripe.OAuth.token.
    """
    creds = get_stripe_connect_credentials(event)
    secret_key = creds.get('secret_key')
    if not secret_key:
        raise ValueError(_('Stripe Connect secret key is not configured on this platform.'))

    resp = stripe.OAuth.token(
        grant_type='authorization_code',
        code=code,
        api_key=secret_key,
    )
    return resp


def get_stripe_account_display_name(stripe_user_id: str, event=None) -> str:
    """
    Attempt to retrieve a human-readable display name for the connected Stripe account.
    Falls back to the stripe_user_id.
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

        settings = getattr(acct, 'settings', None) or {}
        dashboard = (
            getattr(settings, 'dashboard', None)
            if hasattr(settings, 'dashboard')
            else (settings.get('dashboard') if isinstance(settings, dict) else None)
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
    except Exception as exc:
        logger.warning('Could not retrieve display name for Stripe account %s: %s', stripe_user_id, exc)

    return stripe_user_id


def deauthorize_stripe_account(*, stripe_user_id: str, event=None) -> None:
    """
    Revoke access to the connected Stripe account if credentials are valid.
    """
    creds = get_stripe_connect_credentials(event)
    secret_key = creds.get('secret_key')
    client_id = creds.get('client_id')
    if not secret_key or not client_id or not stripe_user_id:
        return

    try:
        stripe.OAuth.deauthorize(
            client_id=client_id,
            stripe_user_id=stripe_user_id,
            api_key=secret_key,
        )
    except Exception as exc:
        logger.warning('Could not deauthorize Stripe account %s: %s', stripe_user_id, exc)
