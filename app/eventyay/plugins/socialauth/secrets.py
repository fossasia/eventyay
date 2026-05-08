import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings

logger = logging.getLogger(__name__)

SECRET_PREFIX = 'enc:v1:'
SECRET_CONTEXT = 'eventyay.socialauth.secret'


def is_encrypted_secret(value: str) -> bool:
    return bool(value) and value.startswith(SECRET_PREFIX)


def encrypt_secret(value: str) -> str:
    if not value:
        return value
    if is_encrypted_secret(value):
        return value

    token = get_fernet().encrypt(value.encode('utf-8')).decode('utf-8')
    return f'{SECRET_PREFIX}{token}'


def decrypt_secret(value: str) -> str:
    if not value or not is_encrypted_secret(value):
        return value

    token = value.removeprefix(SECRET_PREFIX)
    try:
        return get_fernet().decrypt(token.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        logger.error('Failed to decrypt social auth secret token.')
        return ''


def get_fernet() -> MultiFernet:
    configured_keys = tuple(getattr(settings, 'SOCIALAUTH_SECRET_ENCRYPTION_KEYS', ()) or ())
    fernet_keys = tuple(_to_fernet_key(key) for key in configured_keys) or (_derived_default_key(),)
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
