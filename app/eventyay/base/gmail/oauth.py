import logging
from urllib.parse import urlencode

import requests
from django.core import signing
from django.utils.translation import gettext_lazy as _

from eventyay.base.gmail.constants import (
    GMAIL_OAUTH_AUTHORIZE_URL,
    GMAIL_OAUTH_SCOPE,
    GMAIL_OAUTH_SCOPES,
    GMAIL_OAUTH_TOKEN_URL,
    GMAIL_SEND_SCOPE,
)
from eventyay.base.gmail.deps import require_google_api_dependencies
from eventyay.base.gmail.errors import (
    GmailDailyLimitError,
    GmailPermanentError,
    GmailRateLimitError,
    GmailTemporaryError,
)
from eventyay.base.gmail.models import GmailOAuthCredential
from eventyay.base.settings import GlobalSettingsObject


logger = logging.getLogger(__name__)

GMAIL_OAUTH_STATE_SALT = 'eventyay.gmail.oauth'
GMAIL_OAUTH_STATE_MAX_AGE = 600


def get_gmail_client_config():
    gs = GlobalSettingsObject()
    client_id = gs.settings.get('gmail_client_id', default='')
    client_secret = gs.settings.get('gmail_client_secret', default='')
    if not client_id or not client_secret:
        raise ValueError(_('Gmail OAuth client ID and secret must be configured in global settings.'))
    return client_id, client_secret


def build_oauth_state(*, event_id=None, user_id=None, next_url='') -> str:
    payload = {
        'event_id': event_id,
        'user_id': user_id,
        'next_url': next_url,
    }
    return signing.dumps(payload, salt=GMAIL_OAUTH_STATE_SALT)


def load_oauth_state(state: str) -> dict:
    return signing.loads(state, salt=GMAIL_OAUTH_STATE_SALT, max_age=GMAIL_OAUTH_STATE_MAX_AGE)


def build_authorization_url(*, redirect_uri: str, state: str) -> str:
    client_id, _ = get_gmail_client_config()
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': GMAIL_OAUTH_SCOPE,
        'access_type': 'offline',
        'prompt': 'consent',
        'include_granted_scopes': 'true',
        'state': state,
    }
    return f'{GMAIL_OAUTH_AUTHORIZE_URL}?{urlencode(params)}'


def exchange_authorization_code(*, code: str, redirect_uri: str) -> dict:
    client_id, client_secret = get_gmail_client_config()
    response = requests.post(
        GMAIL_OAUTH_TOKEN_URL,
        data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if GMAIL_SEND_SCOPE not in data.get('scope', ''):
        raise ValueError(_('The required Gmail send permission was not granted.'))
    return data


def fetch_sender_email(access_token: str) -> str:
    response = requests.get(
        'https://openidconnect.googleapis.com/v1/userinfo',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    email = payload.get('email')
    if not email:
        raise ValueError(_('Google did not return an email address for the connected account.'))
    return email


def build_google_credentials(credential: GmailOAuthCredential):
    Request, Credentials, _, _ = require_google_api_dependencies()
    client_id, client_secret = get_gmail_client_config()
    creds = Credentials(
        token=credential.get_access_token() or None,
        refresh_token=credential.get_refresh_token(),
        token_uri=GMAIL_OAUTH_TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        scopes=list(GMAIL_OAUTH_SCOPES),
        expiry=credential.token_expiry,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        credential.update_access_token(creds.token, creds.expiry)
    return creds


def build_gmail_service(credential: GmailOAuthCredential):
    _, _, build, _ = require_google_api_dependencies()
    creds = build_google_credentials(credential)
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def classify_http_error(error):
    _, _, _, HttpError = require_google_api_dependencies()
    if not isinstance(error, HttpError):
        raise error

    status = error.resp.status if error.resp else None
    reason = ''
    if error.error_details:
        reason = error.error_details[0].get('reason', '')
    message = str(error)

    if status in (429,) or reason in {'rateLimitExceeded', 'userRateLimitExceeded'}:
        raise GmailRateLimitError(message) from error
    if status in (403,) and reason in {'dailyLimitExceeded', 'quotaExceeded'}:
        raise GmailDailyLimitError(message) from error
    if status in (400, 401, 403) and reason in {'invalid_grant', 'authError', 'failedPrecondition'}:
        raise GmailPermanentError(message) from error
    if status in (500, 502, 503, 504):
        raise GmailTemporaryError(message) from error
    if status and status >= 500:
        raise GmailTemporaryError(message) from error
    raise GmailPermanentError(message) from error
