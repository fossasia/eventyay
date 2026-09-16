class GmailEmailError(Exception):
    """Base class for Gmail API email delivery errors."""


class GmailTemporaryError(GmailEmailError):
    """Temporary Gmail API error that should be retried with backoff."""


class GmailRateLimitError(GmailTemporaryError):
    """Gmail API or per-account rate limit exceeded."""


class GmailDailyLimitError(GmailEmailError):
    """Daily sending limit reached for the connected Gmail/Workspace account."""


class GmailPermanentError(GmailEmailError):
    """Permanent rejection that should not be retried endlessly."""
