"""Tests for the Event Settings Contact Organizer configuration."""

import pytest
from django.test import override_settings
from django.urls import reverse
from django_scopes import scope


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_contact_organizer_settings_rendering(organizer_client, event):
    """Verify that Contact Organizer label, checkbox, and helper text render with accessible attributes."""
    url = reverse('eventyay_common:event.update', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = organizer_client.get(url)
    assert response.status_code == 200

    content = response.content.decode('utf-8')
    assert 'Contact Organizer' in content
    assert 'Enable attendees to contact organizers' in content
    assert 'This option enables a contact form that attendees can use to contact an organizer.' in content
    assert 'id_settings-contact_form_enabled' in content
    assert 'id="id_settings-contact_form_enabled_helptext"' in content
    assert 'for="id_settings-contact_form_enabled"' in content
    assert 'contact-form-email-fields' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_contact_organizer_settings_save(organizer_client, event):
    """Verify that enabling the contact form and providing a valid email saves to event settings."""
    url = reverse('eventyay_common:event.update', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = organizer_client.post(
        url,
        {
            'name_0': 'Updated Event Name',
            'slug': event.slug,
            'date_from_0': '2026-11-01',
            'date_from_1': '09:00:00',
            'date_to_0': '2026-11-03',
            'date_to_1': '18:00:00',
            'settings-timezone': 'UTC',
            'settings-locale': 'en',
            'settings-locales': ['en'],
            'settings-contact_form_enabled': 'on',
            'settings-contact_mail': 'organizer@example.com',
            'header-links-TOTAL_FORMS': '0',
            'header-links-INITIAL_FORMS': '0',
            'footer-links-TOTAL_FORMS': '0',
            'footer-links-INITIAL_FORMS': '0',
        },
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        event.settings.flush()
        assert event.settings.get('contact_form_enabled') is True
        assert event.settings.get('contact_mail') == 'organizer@example.com'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_contact_organizer_validation_error_when_email_missing(organizer_client, event):
    """Verify that enabling the contact form without an email address triggers a form validation error."""
    url = reverse('eventyay_common:event.update', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    response = organizer_client.post(
        url,
        {
            'name_0': 'Updated Event Name',
            'slug': event.slug,
            'date_from_0': '2026-11-01',
            'date_from_1': '09:00:00',
            'date_to_0': '2026-11-03',
            'date_to_1': '18:00:00',
            'settings-timezone': 'UTC',
            'settings-locale': 'en',
            'settings-locales': ['en'],
            'settings-contact_form_enabled': 'on',
            'settings-contact_mail': '',
            'header-links-TOTAL_FORMS': '0',
            'header-links-INITIAL_FORMS': '0',
            'footer-links-TOTAL_FORMS': '0',
            'footer-links-INITIAL_FORMS': '0',
        },
    )
    assert response.status_code == 200
    assert 'Please provide an email address for the contact form.' in response.content.decode('utf-8')
