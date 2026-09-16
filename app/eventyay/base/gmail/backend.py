import base64
import logging

from django.core.mail import EmailMessage
from django.utils.translation import gettext_lazy as _

from eventyay.base.email import _get_test_email_data
from eventyay.base.gmail.deps import require_google_api_dependencies
from eventyay.base.gmail.errors import (
    GmailDailyLimitError,
    GmailPermanentError,
    GmailRateLimitError,
)
from eventyay.base.gmail.models import GmailOAuthCredential


logger = logging.getLogger(__name__)


class GmailAPIEmail:
    def __init__(self, credential: GmailOAuthCredential, fallback_backend=None):
        self.credential = credential
        self.fallback_backend = fallback_backend

    def test(self, from_addr, to_addrs=None, reply_to=None):
        to_addrs, subject, body, headers = _get_test_email_data(from_addr, to_addrs, reply_to)
        message = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_addr,
            to=to_addrs,
            headers=headers,
        )
        self.send_messages([message])

    def send_messages(self, emails):
        sent = 0
        for email in emails:
            sent += self._send_single(email)
        return sent

    def _send_single(self, email) -> int:
        from eventyay.base.gmail.oauth import build_gmail_service, classify_http_error

        recipient_count = len(email.to or []) + len(email.cc or []) + len(email.bcc or [])
        if recipient_count <= 0:
            recipient_count = 1

        if not self.credential.can_send(recipient_count):
            return self._handle_limit(
                GmailDailyLimitError(
                    _('Daily Gmail sending limit reached for %(email)s.')
                    % {'email': self.credential.sender_email}
                ),
                email,
            )

        if self.credential.rate_limit_exceeded():
            return self._handle_limit(
                GmailRateLimitError(
                    _('Gmail rate limit reached for %(email)s.')
                    % {'email': self.credential.sender_email}
                ),
                email,
            )

        raw_message = email.message().as_bytes()
        encoded_message = base64.urlsafe_b64encode(raw_message).decode()

        try:
            _, _, _, HttpError = require_google_api_dependencies()
            service = build_gmail_service(self.credential)
            service.users().messages().send(userId='me', body={'raw': encoded_message}).execute()
            self.credential.record_send(recipient_count)
            return 1
        except Exception as exc:
            _, _, _, HttpError = require_google_api_dependencies()
            if isinstance(exc, HttpError) and exc.resp.status == 401:
                logger.warning("Got 401 from Gmail API, attempting to refresh token before permanent failure.")
                from eventyay.base.gmail.oauth import build_google_credentials
                from google.auth.transport.requests import Request
                try:
                    creds = build_google_credentials(self.credential)
                    creds.refresh(Request())
                    self.credential.update_access_token(creds.token, creds.expiry)
                    
                    service = build_gmail_service(self.credential)
                    service.users().messages().send(userId='me', body={'raw': encoded_message}).execute()
                    self.credential.record_send(recipient_count)
                    return 1
                except Exception as refresh_exc:
                    logger.warning("Failed to refresh token after 401: %s", refresh_exc)

            self.credential.set_last_error(str(exc))
            if isinstance(exc, HttpError):
                try:
                    classify_http_error(exc)
                except (GmailPermanentError, GmailDailyLimitError) as limit_error:
                    return self._handle_limit(limit_error, email)
            raise

    def _handle_limit(self, error, email) -> int:
        if self.fallback_backend is None:
            raise error
        logger.warning(
            'Gmail delivery failed for %s, falling back to alternate provider: %s',
            self.credential.sender_email,
            error,
        )
        return self.fallback_backend.send_messages([email]) or 0

    @property
    def retry_countdown(self) -> int:
        if self.credential.rate_limit_exceeded():
            return self.credential.seconds_until_rate_limit_reset()
        return min(self.credential.seconds_until_daily_reset(), 300)
