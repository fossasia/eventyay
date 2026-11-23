import pytest
from django.core import mail

@pytest.mark.django_db
class TestContactOrganizer:
    """Test contact organizer functionality."""

    def test_contact_organizer_unauthenticated(self, client, organizer, event):
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = client.post(url, {
            'message': 'Hello, this is a test message.',
        })
        assert response.status_code == 401
        assert response.json()['success'] is False
        assert 'logged in' in response.json()['error']

    def test_contact_organizer_authenticated_missing_message(self, authenticated_client, organizer, event):
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = authenticated_client.post(url, {
            'message': '',
        })
        assert response.status_code == 400
        assert response.json()['success'] is False

    def test_contact_organizer_authenticated_success(self, authenticated_client, organizer, event, user):
        # Configure event contact email so it doesn't return 400
        event.settings.contact_mail = 'contact@example.com'
        
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = authenticated_client.post(url, {
            'message': 'This is a valid long enough message.',
        })
        assert response.status_code == 200
        assert response.json()['success'] is True

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == ['contact@example.com']
        assert email.reply_to == [user.email]
        assert email.bcc == []

    def test_contact_organizer_authenticated_send_copy(self, authenticated_client, organizer, event, user):
        event.settings.contact_mail = 'contact@example.com'
        
        url = f'/{organizer.slug}/{event.slug}/contact/'
        response = authenticated_client.post(url, {
            'message': 'This is a valid long enough message with send copy.',
            'send_copy': 'on',
        })
        assert response.status_code == 200
        assert response.json()['success'] is True

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == ['contact@example.com']
        assert email.bcc == [user.email]
