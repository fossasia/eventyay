# Masking data for logging purposes.

import random
from collections.abc import Iterable


class EmailMasker:
    """
    Uitlity to mask email address by replacing some characters with asterisks.

    The mask action is delayed until the __str__ method is called, to save computation when log message is not emitted.
    """

    _email: str

    def __init__(self, email: str):
        self._email = email

    def __str__(self) -> str:
        """
        Add some asterisks to random positions in the local part of the email to mask it.
        """
        if not self._email or '@' not in self._email:
            return ''
        local_part, domain = self._email.split('@', 1)
        positions = random.sample(range(len(local_part)), min(2, len(local_part)))  # Randomly select positions to mask
        masked_local = ''.join('*' if i in positions else char for i, char in enumerate(local_part))
        return f'{masked_local}@{domain}'

    def to_json(self) -> str:
        return str(self)

    @classmethod
    def from_multi(cls, emails: Iterable[str]) -> tuple['EmailMasker', ...]:
        return tuple(cls(email) for email in emails)
