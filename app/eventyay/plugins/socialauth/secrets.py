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


def looks_like_encrypted_secret(value: str) -> bool:
    """True if ``value`` has the shape of a Fernet token (may still be undecryptable)."""
    return _is_probably_fernet_token(value)


def is_encrypted_secret(value: str) -> bool:
    """True if ``value`` decrypts with the current encryption keys."""
    if not value or not looks_like_encrypted_secret(value):
        return False
    try:
        get_fernet().decrypt(value.encode('utf-8'))
        return True
    except InvalidToken:
        return False


def encrypt_secret(value: str) -> str:
    if not value:
        return value
    if is_encrypted_secret(value):
        return value
    if looks_like_encrypted_secret(value):
        # Token-shaped but not decryptable with current keys; preserve ciphertext.
        return value
    return get_fernet().encrypt(value.encode('utf-8')).decode('utf-8')


def decrypt_secret(value: str) -> str:
    if not value:
        return value
    if not looks_like_encrypted_secret(value):
        # Obviously not a Fernet token; return plaintext as-is.
        return value
    try:
        return get_fernet().decrypt(value.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        # Passes the shape check but is not decryptable with current keys.
        # Could be a plaintext secret that matched the heuristic, or ciphertext
        # from a rotated key. Log and return empty rather than exposing raw bytes.
        logger.warning(
            'Failed to decrypt social auth secret (length %s). '
            'If encryption keys changed, set SOCIALAUTH_SECRET_ENCRYPTION_KEYS and re-encrypt stored secrets.',
            len(value),
        )
        return ''


@functools.lru_cache(maxsize=1)
def get_fernet() -> MultiFernet:
    configured_fernet_keys = tuple(_to_fernet_key(key) for key in _configured_encryption_key_strings())
    derived_default_key = _derived_default_key()
    if derived_default_key in configured_fernet_keys:
        fernet_keys = configured_fernet_keys
    else:
        fernet_keys = configured_fernet_keys + (derived_default_key,)
    return MultiFernet(tuple(Fernet(key) for key in fernet_keys))


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
