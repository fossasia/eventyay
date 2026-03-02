# Masking data for logging purposes.

from collections.abc import Iterable


class EmailMasker:
    """
    Utility to mask email address by replacing some characters with asterisks.

    The mask action is delayed until the __str__ method is called, to save computation when log message is not emitted.
    Uses deterministic masking for consistent log correlation.
    """

    _email: str

    def __init__(self, email: str):
        self._email = email

    def __str__(self) -> str:
        """
        Mask characters at odd positions (1, 3, 5...) in the local part of the email.
        This provides deterministic masking for consistent log correlation while
        still protecting user privacy by hiding approximately half of the local part.
        """
        if not self._email or '@' not in self._email:
            return ''
        local_part, domain = self._email.split('@', 1)
        # Mask characters at odd positions (index 1, 3, 5, ...)
        masked_local = ''.join('*' if i % 2 == 1 else char for i, char in enumerate(local_part))
        return f'{masked_local}@{domain}'

    def __repr__(self) -> str:
        return str(self)

    def to_json(self) -> str:
        return str(self)

    @classmethod
    def from_multi(cls, emails: Iterable[str]) -> tuple['EmailMasker', ...]:
        return tuple(cls(email) for email in emails)