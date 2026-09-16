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

def test_classify_http_error():
    from eventyay.base.gmail.oauth import classify_http_error
    from eventyay.base.gmail.errors import GmailRateLimitError, GmailDailyLimitError, GmailPermanentError, GmailTemporaryError
    from eventyay.base.gmail.deps import require_google_api_dependencies
    import json
    
    _, _, _, HttpError = require_google_api_dependencies()
    
    class FakeResponse:
        def __init__(self, status):
            self.status = status
            
    resp = FakeResponse(429)
    content = json.dumps({'error': {'errors': [{'reason': 'rateLimitExceeded'}], 'message': 'Rate limit'}}).encode('utf-8')
    err = HttpError(resp, content)
    
    with pytest.raises(GmailRateLimitError):
        classify_http_error(err)
        
    resp = FakeResponse(403)
    content = json.dumps({'error': {'errors': [{'reason': 'dailyLimitExceeded'}], 'message': 'Daily limit'}}).encode('utf-8')
    err = HttpError(resp, content)
    
    with pytest.raises(GmailDailyLimitError):
        classify_http_error(err)
        
    resp = FakeResponse(400)
    content = json.dumps({'error': {'errors': [{'reason': 'invalid_grant'}], 'message': 'Bad auth'}}).encode('utf-8')
    err = HttpError(resp, content)
    
    with pytest.raises(GmailPermanentError):
        classify_http_error(err)

    resp = FakeResponse(502)
    content = b''
    err = HttpError(resp, content)
    
    with pytest.raises(GmailTemporaryError):
        classify_http_error(err)

@pytest.mark.django_db
def test_gmail_disconnect_revokes_token():
    credential = GmailOAuthCredential.objects.create(
        sender_email='organizer@example.com',
        encrypted_refresh_token=encrypt_value('refresh-token'),
    )
    with patch('requests.post') as mock_post:
        credential.disconnect()
        mock_post.assert_called_once_with('https://oauth2.googleapis.com/revoke', params={'token': 'refresh-token'}, timeout=5)
        credential.refresh_from_db()
        assert not credential.is_active
        assert not credential.get_refresh_token()

@pytest.mark.django_db
def test_mail_send_task_retries_on_gmail_rate_limit():
    from eventyay.base.services.mail import mail_send_task
    from eventyay.base.gmail.errors import GmailRateLimitError
    
    with patch('eventyay.base.services.mail.get_mail_backend') as mock_get_backend:
        mock_backend = mock_get_backend.return_value
        mock_backend.send_messages.side_effect = GmailRateLimitError("Rate limited")
        mock_backend.retry_countdown = 60
        
        with patch.object(mail_send_task, 'retry') as mock_retry:
            mail_send_task(
                to=['user@example.com'],
                subject='Test',
                body='Test body',
                html=None,
                sender='sender@example.com',
            )
            mock_retry.assert_called_once()
            args, kwargs = mock_retry.call_args
            assert 'countdown' in kwargs


@pytest.mark.django_db
def test_gmail_oauth_views_require_admin(client):
    response = client.get('/control/global/settings/gmail/connect')
    assert response.status_code == 302
    assert '/control/login' in response.url

@pytest.mark.django_db
def test_event_gmail_oauth_views_require_permission(client):
    response = client.get('/control/event/organizer/event/settings/gmail/connect')
    assert response.status_code == 302
    assert '/control/login' in response.url
