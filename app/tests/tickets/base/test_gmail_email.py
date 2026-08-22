from datetime import date
from unittest.mock import patch

import pytest
from django.test import override_settings

from eventyay.base.gmail.crypto import decrypt_value, encrypt_value
from eventyay.base.gmail.models import GmailOAuthCredential
from eventyay.base.gmail.oauth import fetch_sender_email


@pytest.mark.django_db
def test_gmail_token_encryption_roundtrip():
    token = 'refresh-token-value'
    encrypted = encrypt_value(token)
    assert encrypted != token
    assert decrypt_value(encrypted) == token


@pytest.mark.django_db
def test_gmail_daily_quota_tracking():
    credential = GmailOAuthCredential.objects.create(
        sender_email='organizer@example.com',
        encrypted_refresh_token=encrypt_value('refresh'),
    )
    credential.daily_send_count_date = date.today()
    credential.daily_send_count = credential.daily_send_limit - 1
    credential.save()

    assert credential.can_send()
    credential.record_send()
    assert not credential.can_send()


@pytest.mark.django_db
@override_settings(GMAIL_DAILY_SEND_LIMIT=10)
def test_gmail_daily_limit_respected():
    credential = GmailOAuthCredential.objects.create(
        sender_email='organizer@example.com',
        encrypted_refresh_token=encrypt_value('refresh'),
        daily_send_count=10,
        daily_send_count_date=date.today(),
    )
    assert credential.remaining_daily_quota() == 0
    assert not credential.can_send()


def test_fetch_sender_email_reads_openid_userinfo():
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {'email': 'sender@example.com'}

    with patch('eventyay.base.gmail.oauth.requests.get', return_value=FakeResponse()) as get:
        assert fetch_sender_email('access-token') == 'sender@example.com'

    get.assert_called_once_with(
        'https://openidconnect.googleapis.com/v1/userinfo',
        headers={'Authorization': 'Bearer access-token'},
        timeout=30,
    )
