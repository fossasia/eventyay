"""
Placeholders that replace personal data when ticketing data is anonymized.

Placeholder addresses use the reserved ``.invalid`` top-level domain (RFC 2606), so they can never
receive mail, cannot be verified by anyone signing up with them, and are easy to recognise.
"""

import string
from collections.abc import Iterable
from email.utils import parseaddr

from django.utils.crypto import get_random_string


ANONYMIZED_EMAIL_DOMAIN = 'eventyay.invalid'
ANONYMIZED_NAME = 'Anonymized'


def anonymized_email(kind: str) -> str:
    """
    A new placeholder address such as ``order.k3f9q2xa7m@eventyay.invalid``. The random part keeps
    placeholders unique, so anonymized orders and attendees are never merged with each other, and
    unguessable, so nobody can claim one.
    """
    token = get_random_string(10, string.ascii_lowercase + string.digits)
    return f'{kind}.{token}@{ANONYMIZED_EMAIL_DOMAIN}'


def is_anonymized_email(address: str | None) -> bool:
    """
    Whether ``address`` is a placeholder. The mailbox is parsed first, so a display name such as
    ``Anonymous <order.k3f9q2xa7m@eventyay.invalid>`` is recognised and the domain must match exactly.
    """
    if not address:
        return False
    _, at_sign, domain = parseaddr(address)[1].lower().rpartition('@')
    return bool(at_sign) and domain == ANONYMIZED_EMAIL_DOMAIN


def without_anonymized_emails(addresses: Iterable[str]) -> list[str]:
    return [address for address in addresses if not is_anonymized_email(address)]
