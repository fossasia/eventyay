"""Etherpad collaborative notes integration.

This module builds and (optionally) creates Etherpad pads for sessions.

Pad *content* always lives on the configured Etherpad instance, never inside
eventyay. We only store the resulting pad URL on the session.

Two modes of operation:

* **API mode** — when a platform API key is configured, pads are created
  through the Etherpad HTTP API so we can guarantee the pad exists.
* **Link-only mode** — when no API key is configured, we still build a
  deterministic, safe pad URL. Etherpad creates the pad lazily on first visit.

The API key is read from global settings on the server side only and is never
exposed to the frontend.
"""

import re
from urllib.parse import quote, urljoin

import requests
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

# Etherpad HTTP API version shipped by current Etherpad releases.
ETHERPAD_API_VERSION = '1.2.15'

# Pad IDs may not contain characters that are unsafe in URLs or that Etherpad
# rejects. We keep things conservative: letters, digits, dash and underscore.
_UNSAFE_PAD_CHARS = re.compile(r'[^A-Za-z0-9_-]+')
_PAD_TOKEN_CHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

# Etherpad pad IDs are limited in length; keep generated names well below it.
MAX_PAD_NAME_LENGTH = 50


class EtherpadError(Exception):
    """Raised when an Etherpad pad cannot be created or configured."""


class EtherpadConfigurationError(EtherpadError):
    """Raised when the Etherpad integration is not configured correctly."""


def validate_etherpad_url(value):
    """Validate that ``value`` is a usable http(s) Etherpad base/instance URL.

    Raises django ``ValidationError`` on failure so it can be reused from forms.
    """
    if not value:
        return
    URLValidator(schemes=['http', 'https'])(value)


def sanitize_pad_segment(value):
    """Turn an arbitrary string into a safe pad-name segment."""
    cleaned = _UNSAFE_PAD_CHARS.sub('-', str(value or '')).strip('-')
    return cleaned


def generate_pad_token(length=8):
    return get_random_string(length=length, allowed_chars=_PAD_TOKEN_CHARS)


def build_pad_name(event, submission, *, pattern, token=None):
    """Build a safe, stable pad name from the configured pattern.

    We deliberately avoid relying on the public session title: a stable pattern
    of event slug + submission code + random token keeps pad names predictable,
    safe, and not guessable from the title alone.
    """
    token = token or generate_pad_token()
    safe_default = f'{event.slug}-{submission.code}-{token}'
    try:
        raw = (pattern or '{event}-{submission}-{token}').format(
            event=event.slug,
            submission=submission.code,
            token=token,
        )
    except (KeyError, IndexError, ValueError):
        raw = safe_default
    name = sanitize_pad_segment(raw)
    if not name:
        name = sanitize_pad_segment(safe_default)
    return name[:MAX_PAD_NAME_LENGTH].strip('-')


def build_pad_url(base_url, pad_name):
    """Build the public pad URL for a pad name on a given instance."""
    base = base_url.rstrip('/') + '/'
    return urljoin(base, 'p/' + quote(pad_name, safe=''))


def _create_pad_via_api(base_url, api_key, pad_name):
    """Create a pad through the Etherpad HTTP API.

    Returns silently if the pad already exists (so re-running is safe).
    """
    endpoint = urljoin(
        base_url.rstrip('/') + '/',
        f'api/{ETHERPAD_API_VERSION}/createPad',
    )
    try:
        response = requests.get(
            endpoint,
            params={'apikey': api_key, 'padID': pad_name},
            timeout=(5, 10),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise EtherpadError(
            _('Could not reach the Etherpad instance: {error}').format(error=str(exc))
        ) from exc
    except ValueError as exc:
        raise EtherpadError(
            _('The Etherpad instance returned an unexpected response.')
        ) from exc

    code = payload.get('code')
    # code 0 = success. code 1 with "padID does already exist" is fine for us.
    if code == 0:
        return
    message = payload.get('message', '')
    if code == 1 and 'already exist' in message.lower():
        return
    raise EtherpadError(
        _('Etherpad rejected the pad creation: {message}').format(message=message or _('unknown error'))
    )


def generate_pad_for_submission(event, submission, *, force=False):
    """Generate (and persist) an Etherpad URL for a session.

    Returns the pad URL. Does not overwrite an existing URL unless ``force`` is
    given — callers must confirm before replacing existing notes.

    Raises :class:`EtherpadConfigurationError` if the integration is not usable,
    and :class:`EtherpadError` if pad creation fails.
    """
    from eventyay.base.settings import GlobalSettingsObject

    if submission.etherpad_url and not force:
        raise EtherpadError(
            _('This session already has an Etherpad link. Confirm replacement before regenerating.')
        )

    gs = GlobalSettingsObject().settings
    if not gs.etherpad_enabled:
        raise EtherpadConfigurationError(_('Etherpad integration is disabled on this platform.'))

    base_url = (gs.etherpad_base_url or '').strip()
    if not base_url:
        raise EtherpadConfigurationError(_('No Etherpad instance URL is configured.'))
    try:
        validate_etherpad_url(base_url)
    except ValidationError as exc:
        raise EtherpadConfigurationError(_('The configured Etherpad instance URL is invalid.')) from exc

    pad_name = build_pad_name(event, submission, pattern=gs.etherpad_pad_name_pattern)

    api_key = (gs.etherpad_api_key or '').strip()
    if api_key:
        _create_pad_via_api(base_url, api_key, pad_name)

    return build_pad_url(base_url, pad_name)
