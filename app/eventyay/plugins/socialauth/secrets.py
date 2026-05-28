"""Encrypt and decrypt OAuth client secrets for the socialauth plugin.

Uses Fernet via ``SOCIALAUTH_SECRET_ENCRYPTION_KEYS`` when that setting is set.

When ``SOCIALAUTH_SECRET_ENCRYPTION_KEYS`` is unset, a key derived from
``settings.SECRET_KEY`` is used as a fallback. Rotating ``SECRET_KEY`` without
also configuring and migrating ``SOCIALAUTH_SECRET_ENCRYPTION_KEYS`` makes
existing ciphertext undecryptable (``decrypt_secret`` then returns ``''`` after
logging). Production deployments should set explicit encryption keys that are
managed independently of ``SECRET_KEY``.
"""

import base64
import functools
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

logger = logging.getLogger(__name__)

SECRET_CONTEXT = 'eventyay.socialauth.secret'
ENCRYPTED_PREFIX = 'fernet:'


def _configured_encryption_key_strings() -> tuple[str, ...]:
    raw = getattr(settings, 'SOCIALAUTH_SECRET_ENCRYPTION_KEYS', ()) or ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, (bytes, bytearray)):
        logger.error('SOCIALAUTH_SECRET_ENCRYPTION_KEYS must be strings, not bytes; ignoring.')
        return ()
    if not isinstance(raw, (list, tuple)):
        logger.error(
            'SOCIALAUTH_SECRET_ENCRYPTION_KEYS must be an iterable of strings, got %s.',
            type(raw).__name__,
        )
        return ()
    keys: list[str] = []
    for index, key in enumerate(raw):
        if not isinstance(key, str):
            logger.error(
                'SOCIALAUTH_SECRET_ENCRYPTION_KEYS[%s] must be a string, got %s; skipping.',
                index,
                type(key).__name__,
            )
            continue
        if not key:
            logger.error('SOCIALAUTH_SECRET_ENCRYPTION_KEYS[%s] must be non-empty; skipping.', index)
            continue
        keys.append(key)
    return tuple(keys)


def _encrypted_token(value: str) -> str:
    if value.startswith(ENCRYPTED_PREFIX):
        return value[len(ENCRYPTED_PREFIX) :]
    return value


def looks_like_encrypted_secret(value: str) -> bool:
    """True if ``value`` is marked or shaped like Fernet ciphertext (may still be undecryptable)."""
    if value.startswith(ENCRYPTED_PREFIX):
        return True
    return _is_probably_fernet_token(value)


def is_encrypted_secret(value: str) -> bool:
    """True if ``value`` decrypts with the current encryption keys."""
    if not value or not looks_like_encrypted_secret(value):
        return False
    try:
        get_fernet().decrypt(_encrypted_token(value).encode('utf-8'))
        return True
    except InvalidToken:
        return False


def encrypt_secret(value: str) -> str:
    if not value:
        return value
    if value.startswith(ENCRYPTED_PREFIX):
        return value
    if is_encrypted_secret(value):
        return f'{ENCRYPTED_PREFIX}{_encrypted_token(value)}'
    if _is_probably_fernet_token(value):
        # Legacy ciphertext from another key; preserve without re-encrypting.
        return value
    token = get_fernet().encrypt(value.encode('utf-8')).decode('utf-8')
    return f'{ENCRYPTED_PREFIX}{token}'


def decrypt_secret(value: str) -> str:
    if not value:
        return value
    if value.startswith(ENCRYPTED_PREFIX):
        try:
            return get_fernet().decrypt(_encrypted_token(value).encode('utf-8')).decode('utf-8')
        except InvalidToken:
            logger.warning(
                'Failed to decrypt social auth secret (length %s). '
                'If encryption keys changed, set SOCIALAUTH_SECRET_ENCRYPTION_KEYS and re-encrypt stored secrets.',
                len(value),
            )
            return ''
    if not _is_probably_fernet_token(value):
        return value
    try:
        return get_fernet().decrypt(value.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        logger.warning(
            'Failed to decrypt social auth secret (length %s). '
            'If encryption keys changed, set SOCIALAUTH_SECRET_ENCRYPTION_KEYS and re-encrypt stored secrets.',
            len(value),
        )
        return ''


@functools.lru_cache(maxsize=8)
def _get_fernet_for_settings(secret_key: str, configured_keys: tuple[str, ...]) -> MultiFernet:
    configured_fernet_keys = tuple(_to_fernet_key(key) for key in configured_keys)
    derived_default_key = _derive_fernet_key(secret_key)
    if derived_default_key in configured_fernet_keys:
        fernet_keys = configured_fernet_keys
    else:
        fernet_keys = configured_fernet_keys + (derived_default_key,)
    return MultiFernet(tuple(Fernet(key) for key in fernet_keys))


def get_fernet() -> MultiFernet:
    return _get_fernet_for_settings(
        settings.SECRET_KEY,
        _configured_encryption_key_strings(),
    )


def _to_fernet_key(key: str) -> bytes:
    try:
        normalized = key.encode('ascii')
        Fernet(normalized)
        return normalized
    except (UnicodeEncodeError, ValueError):
        return _derive_fernet_key(key)


def _derived_default_key() -> bytes:
    """Fallback Fernet key derived from ``SECRET_KEY`` (see module docstring)."""
    return _derive_fernet_key(settings.SECRET_KEY)


def _derive_fernet_key(source: str) -> bytes:
    digest = hashlib.sha256(f'{SECRET_CONTEXT}:{source}'.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def _is_probably_fernet_token(token: str) -> bool:
    if not token:
        return False
    try:
        padding = '=' * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(f'{token}{padding}'.encode('ascii'))
    except (UnicodeEncodeError, ValueError):
        return False
    return bool(decoded) and decoded.startswith(b'\x80')
