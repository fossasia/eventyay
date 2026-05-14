import base64
import functools
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

logger = logging.getLogger(__name__)

SECRET_CONTEXT = 'eventyay.socialauth.secret'


def is_encrypted_secret(value: str) -> bool:
    if not value:
        return False
    return _is_probably_fernet_token(value)


def encrypt_secret(value: str) -> str:
    if not value:
        return value
    if is_encrypted_secret(value):
        return value

    token = get_fernet().encrypt(value.encode('utf-8')).decode('utf-8')
    return token


def decrypt_secret(value: str) -> str:
    if not value or not is_encrypted_secret(value):
        return value

    try:
        return get_fernet().decrypt(value.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        logger.error(
            'Failed to decrypt social auth secret token (length %s).',
            len(value),
        )
        return ''


@functools.lru_cache(maxsize=1)
def get_fernet() -> MultiFernet:
    configured_keys = tuple(getattr(settings, 'SOCIALAUTH_SECRET_ENCRYPTION_KEYS', ()) or ())
    configured_fernet_keys = tuple(_to_fernet_key(key) for key in configured_keys)
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
