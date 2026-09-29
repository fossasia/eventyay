from eventyay.base.operational_logging import OUTCOME_FAILURE, log_event


class GmailEmailError(Exception):
    """Base class for Gmail API email delivery errors."""

    error_code = 'gmail_error'

    def __init__(self, *args):
        super().__init__(*args)
        log_event('mail', 'mail.send', OUTCOME_FAILURE, error_code=self.error_code)


class GmailTemporaryError(GmailEmailError):
    """Temporary Gmail API error that should be retried with backoff."""

    error_code = 'gmail_temporary'


class GmailRateLimitError(GmailTemporaryError):
    """Gmail API or per-account rate limit exceeded."""

    error_code = 'gmail_rate_limit'


class GmailDailyLimitError(GmailEmailError):
    """Daily sending limit reached for the connected Gmail/Workspace account."""

    error_code = 'gmail_daily_limit'


class GmailPermanentError(GmailEmailError):
    """Permanent rejection that should not be retried endlessly."""

    error_code = 'gmail_permanent'

    def __init__(self, *args):
        Exception.__init__(self, *args)
        log_event('mail', 'mail.bounce', OUTCOME_FAILURE, error_code=self.error_code)
