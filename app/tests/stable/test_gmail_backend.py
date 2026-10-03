from unittest.mock import MagicMock, patch

import pytest
from django.core.mail import EmailMessage

from eventyay.base.gmail.backend import GmailAPIEmail
from eventyay.base.gmail.errors import GmailDailyLimitError


def _credential(can_send=True):
    credential = MagicMock(sender_email='organizer@example.com')
    credential.can_send.return_value = can_send
    credential.rate_limit_exceeded.return_value = False
    return credential


def _email():
    return EmailMessage(subject='Hi', body='Hello', from_email='organizer@example.com', to=['buyer@example.org'])


def test_send_single_reports_the_daily_limit():
    backend = GmailAPIEmail(_credential(can_send=False))

    with pytest.raises(GmailDailyLimitError, match='Daily Gmail sending limit reached for organizer@example.com.'):
        backend.send_messages([_email()])


def test_send_single_raises_import_error_when_google_libraries_are_missing():
    credential = _credential()
    backend = GmailAPIEmail(credential)

    with (
        patch('eventyay.base.gmail.backend.require_google_api_dependencies', side_effect=ImportError('missing')),
        patch('eventyay.base.gmail.oauth.build_gmail_service') as build_gmail_service,
        pytest.raises(ImportError, match='missing'),
    ):
        backend.send_messages([_email()])

    build_gmail_service.assert_not_called()
    credential.record_send.assert_not_called()
