from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils.timezone import now

from eventyay.base.models import User
from eventyay.base.settings import GlobalSettingsObject


@pytest.fixture
def admin_user():
    return User.objects.create_user('admin@example.com', 'dummy', is_staff=True)


@pytest.fixture
def staff_client(client, admin_user):
    client.force_login(admin_user)
    admin_user.staffsession_set.create(
        date_start=now(),
        session_key=client.session.session_key,
    )
    return client


@pytest.fixture
def test_email_url():
    return reverse('eventyay_admin:admin.global.settings.test_email')


@pytest.fixture
def smtp_settings(db):
    """Configure a minimal valid SMTP setup in GlobalSettings."""
    gs = GlobalSettingsObject()
    gs.settings.set('mail_from', 'noreply@example.com')
    gs.settings.set('email_vendor', 'smtp')
    gs.settings.set('smtp_host', 'smtp.example.com')
    gs.settings.set('smtp_port', '587')
    gs.settings.set('smtp_username', '')
    gs.settings.set('smtp_password', '')
    gs.settings.set('smtp_use_tls', False)
    gs.settings.set('smtp_use_ssl', False)
    return gs



AJAX_HEADERS = {
    'HTTP_ACCEPT': 'application/json',
    'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest',
}


@pytest.mark.django_db
class TestTestEmailViewJsonPath:
    def test_success_smtp(self, staff_client, test_email_url, smtp_settings):
        with patch(
            'eventyay.control.views.global_settings.CustomSMTPBackend'
        ) as MockBackend:
            instance = MagicMock()
            MockBackend.return_value = instance

            response = staff_client.post(
                test_email_url,
                {'test_email': 'recipient@example.com'},
                **AJAX_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'recipient@example.com' in data['message']

    def test_error_empty_recipient(self, staff_client, test_email_url, smtp_settings):
        response = staff_client.post(
            test_email_url,
            {'test_email': ''},
            **AJAX_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'

    def test_error_invalid_email(self, staff_client, test_email_url, smtp_settings):
        response = staff_client.post(
            test_email_url,
            {'test_email': 'not-an-email'},
            **AJAX_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'
        assert 'not-an-email' in data['message']

    def test_error_missing_smtp_host(self, staff_client, test_email_url):
        gs = GlobalSettingsObject()
        gs.settings.set('mail_from', 'noreply@example.com')
        gs.settings.set('email_vendor', 'smtp')
        gs.settings.set('smtp_host', '')
        gs.settings.set('smtp_port', '')

        response = staff_client.post(
            test_email_url,
            {'test_email': 'recipient@example.com'},
            **AJAX_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'

    def test_error_no_sender_configured(self, staff_client, test_email_url):
        gs = GlobalSettingsObject()
        gs.settings.set('mail_from', '')
        gs.settings.set('email_vendor', 'smtp')

        response = staff_client.post(
            test_email_url,
            {'test_email': 'recipient@example.com'},
            **AJAX_HEADERS,
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'

    def test_error_smtp_exception_returns_json(self, staff_client, test_email_url, smtp_settings):
        import smtplib

        with patch(
            'eventyay.control.views.global_settings.CustomSMTPBackend'
        ) as MockBackend:
            instance = MagicMock()
            instance.send_messages.side_effect = smtplib.SMTPException('connection refused')
            MockBackend.return_value = instance
           
            with patch(
                'eventyay.control.views.global_settings.EmailMessage.send',
                side_effect=smtplib.SMTPException('connection refused'),
            ):
                response = staff_client.post(
                    test_email_url,
                    {'test_email': 'recipient@example.com'},
                    **AJAX_HEADERS,
                )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'error'

    def test_active_tab_not_changed(self, staff_client, test_email_url, smtp_settings):
        """JSON response must not include a Location header (no redirect)."""
        with patch('eventyay.control.views.global_settings.CustomSMTPBackend'):
            with patch('eventyay.control.views.global_settings.EmailMessage.send'):
                response = staff_client.post(
                    test_email_url,
                    {'test_email': 'recipient@example.com'},
                    **AJAX_HEADERS,
                )
        assert response.status_code == 200
        assert 'Location' not in response

    def test_multiple_recipients_accepted(self, staff_client, test_email_url, smtp_settings):
        with patch('eventyay.control.views.global_settings.CustomSMTPBackend'):
            with patch('eventyay.control.views.global_settings.EmailMessage.send'):
                response = staff_client.post(
                    test_email_url,
                    {'test_email': 'a@example.com, b@example.com'},
                    **AJAX_HEADERS,
                )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'a@example.com' in data['message']
        assert 'b@example.com' in data['message']

    def test_gmail_api_success(self, staff_client, test_email_url):
        gs = GlobalSettingsObject()
        gs.settings.set('mail_from', 'noreply@example.com')
        gs.settings.set('email_vendor', 'gmail_api')

        mock_backend = MagicMock()
        with patch(
            'eventyay.base.gmail.resolver.get_gmail_mail_backend',
            return_value=mock_backend,
        ):
            response = staff_client.post(
                test_email_url,
                {'test_email': 'recipient@example.com'},
                **AJAX_HEADERS,
            )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        mock_backend.test.assert_called_once()



@pytest.mark.django_db
class TestTestEmailViewRedirectPath:
    def test_success_redirect_lands_on_email_tab(self, staff_client, test_email_url, smtp_settings):
        with patch('eventyay.control.views.global_settings.CustomSMTPBackend'):
            with patch('eventyay.control.views.global_settings.EmailMessage.send'):
                response = staff_client.post(
                    test_email_url,
                    {'test_email': 'recipient@example.com'},
                )
        assert response.status_code == 302
        settings_url = reverse('eventyay_admin:admin.global.settings')
        assert response['Location'] == f'{settings_url}#tab-email'

    def test_error_redirect_lands_on_email_tab(self, staff_client, test_email_url):
        gs = GlobalSettingsObject()
        gs.settings.set('mail_from', '')

        response = staff_client.post(
            test_email_url,
            {'test_email': 'recipient@example.com'},
        )
        assert response.status_code == 302
        settings_url = reverse('eventyay_admin:admin.global.settings')
        assert response['Location'] == f'{settings_url}#tab-email'

    def test_redirect_does_not_open_meta_data_tab(self, staff_client, test_email_url, smtp_settings):
        """Regression: the old code used #tab3 which resolved to Meta Data."""
        with patch('eventyay.control.views.global_settings.CustomSMTPBackend'):
            with patch('eventyay.control.views.global_settings.EmailMessage.send'):
                response = staff_client.post(
                    test_email_url,
                    {'test_email': 'recipient@example.com'},
                )
        assert '#tab-meta-data' not in response.get('Location', '')
        assert '#tab3' not in response.get('Location', '')



@pytest.mark.django_db
class TestTestEmailViewPermissions:
    def test_anonymous_redirected_to_login(self, client, test_email_url):
        response = client.post(test_email_url, {'test_email': 'x@example.com'})
        assert response.status_code == 302
        assert 'login' in response['Location'].lower()

    def test_non_staff_forbidden(self, client, test_email_url):
        regular = User.objects.create_user('user@example.com', 'dummy')
        client.force_login(regular)
        response = client.post(test_email_url, {'test_email': 'x@example.com'})
        assert response.status_code in (302, 403)
