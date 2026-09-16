import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _get_fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(value: str) -> str:
    if not value:
        return ''
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    if not token:
        return ''
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError('Unable to decrypt stored Gmail credential.') from exc
