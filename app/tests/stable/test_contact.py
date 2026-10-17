import pytest
from bs4 import BeautifulSoup
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django_scopes import scope


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize('enabled', (False, True))
def test_contact_organizer_settings_labels(organizer_client, organizer, event, enabled):
    """Show the requested contact wording and preserve stored checkbox/email values."""
    with scope(event=event):
        event.settings.set('contact_form_enabled', enabled)
        event.settings.set('contact_mail', 'contact@example.com')
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug,
    })
    response = organizer_client.get(url)
    assert response.status_code == 200
    soup = BeautifulSoup(response.content, 'html.parser')
    basics = soup.select_one('.tabbed-form > fieldset')
    assert basics.find('legend').get_text(strip=True) == 'Basics'
    checkbox = basics.find('input', attrs={'name': 'settings-contact_form_enabled'})
    assert checkbox is not None
    assert checkbox.has_attr('checked') is enabled
    row = checkbox.find_parent('div', class_='form-group')
    label = row.find('label', class_='control-label', recursive=False)
    assert label.get_text(strip=True) == 'Contact Organizer'
    assert 'col-md-3' in label['class']
    assert label['for'] == checkbox['id']
    assert checkbox.find_parent('label').get_text(strip=True) == 'Enable attendees to contact organizers'
    column = row.find('div', class_='col-md-9', recursive=False)
    help_text = column.find('p', class_='help-block', recursive=False)
    assert help_text.get_text(strip=True) == (
        'This option enables a contact form that attendees can use to contact an organizer.'
    )
    assert help_text.find_previous_sibling('div', class_='checkbox') is not None
    email_fields = column.find('div', id='contact-form-email-fields')
    email = email_fields.find('input', attrs={'name': 'settings-contact_mail'})
    assert email['value'] == 'contact@example.com'


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
