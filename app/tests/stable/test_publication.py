from unittest.mock import MagicMock

import pytest
from django.test import override_settings
from django.urls import reverse

from eventyay.api.serializers.event import EventSerializer

@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_publication_settings_rendered_in_main_settings(organizer_client, organizer, event):
    """Test that the Publication settings fieldset is rendered on the main event settings page,
    but startpage_visible is NOT included (it is admin-only)."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })
    response = organizer_client.get(url)
    assert response.status_code == 200
    assert b"Publication" in response.content
    assert b"is_public" in response.content
    # startpage_visible must NOT appear in the organiser settings page
    assert b"startpage_visible" not in response.content
    assert b"meta_noindex" in response.content

@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_publication_settings_save_via_main_settings(organizer_client, organizer, event):
    """Test that saving settings on the main settings page works and does NOT change startpage_visible."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })

    # Store original startpage_visible value before the request
    original_startpage_visible = event.startpage_visible

    response = organizer_client.get(url)
    form = response.context['form']
    sform = response.context['sform']
    
    # Assert initial choices are present
    assert 'en' in sform.initial.get('locales', [])
    assert len(sform.fields['locales'].choices) > 0

    # startpage_visible should not be a field the organiser form exposes
    assert 'startpage_visible' not in form.fields

    def build_post_data(enable_publication=True):
        post_data = {
            'name_0': 'Test Event',
            'slug': event.slug,
            'date_from_0': '2026-10-01',
            'date_from_1': '10:00:00',
            'date_to_0': '2026-10-02',
            'date_to_1': '18:00:00',
            'email': event.email,
            'settings-timezone': 'UTC',
            'settings-locale': 'en',
            'settings-locales': ['en'],
            'header-links-TOTAL_FORMS': '0',
            'header-links-INITIAL_FORMS': '0',
            'header-links-MIN_NUM_FORMS': '0',
            'header-links-MAX_NUM_FORMS': '1000',
            'footer-links-TOTAL_FORMS': '0',
            'footer-links-INITIAL_FORMS': '0',
            'footer-links-MIN_NUM_FORMS': '0',
            'footer-links-MAX_NUM_FORMS': '1000',
        }
        if enable_publication:
            post_data['is_public'] = 'on'
            post_data['settings-meta_noindex'] = 'on'
        return post_data

    response = organizer_client.post(url, build_post_data(enable_publication=True), follow=True)

    if response.status_code == 200 and not response.redirect_chain:
        assert False, (
            f"Expected redirect after save, got form errors: "
            f"form={response.context['form'].errors} "
            f"sform={response.context['sform'].errors} "
            f"header_links_formset={response.context['header_links_formset'].errors} "
            f"footer_links_formset={response.context['footer_links_formset'].errors}"
        )

    assert response.status_code == 200
    assert len(response.redirect_chain) > 0, "Enable form submission did not redirect"
    
    event.refresh_from_db()
    event.settings.flush()
    assert event.is_public is True
    # startpage_visible must be unchanged — organisers cannot alter it
    assert event.startpage_visible == original_startpage_visible
    assert event.settings.meta_noindex is True


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_organiser_cannot_change_startpage_visible_via_post(organizer_client, organizer, event):
    """Organisers cannot change startpage_visible by injecting the field into a POST request."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })

    event.startpage_visible = False
    event.save(update_fields=['startpage_visible'])

    post_data = {
        'name_0': 'Test Event',
        'slug': event.slug,
        'date_from_0': '2026-10-01',
        'date_from_1': '10:00:00',
        'date_to_0': '2026-10-02',
        'date_to_1': '18:00:00',
        'email': event.email,
        'settings-timezone': 'UTC',
        'settings-locale': 'en',
        'settings-locales': ['en'],
        'header-links-TOTAL_FORMS': '0',
        'header-links-INITIAL_FORMS': '0',
        'header-links-MIN_NUM_FORMS': '0',
        'header-links-MAX_NUM_FORMS': '1000',
        'footer-links-TOTAL_FORMS': '0',
        'footer-links-INITIAL_FORMS': '0',
        'footer-links-MIN_NUM_FORMS': '0',
        'footer-links-MAX_NUM_FORMS': '1000',
        'startpage_visible': 'on',
    }

    response = organizer_client.post(url, post_data, follow=True)
    assert response.status_code == 200

    event.refresh_from_db()
    assert event.startpage_visible is False


@pytest.mark.django_db
def test_api_serializer_read_only_for_organiser_and_editable_for_admin(event, user):
    """Test that EventSerializer makes startpage_visible read-only for organisers and editable for staff admins."""
    # Regular organiser request context
    user.is_staff = False
    user.is_superuser = False
    org_req = MagicMock(user=user, event=event)
    org_serializer = EventSerializer(event, context={'request': org_req})

    assert org_serializer.fields['startpage_visible'].read_only is True
    assert org_serializer.fields['startpage_featured'].read_only is True

    # Admin request context
    user.is_staff = True
    admin_req = MagicMock(user=user, event=event)
    admin_serializer = EventSerializer(event, context={'request': admin_req})

    assert admin_serializer.fields['startpage_visible'].read_only is False
    assert admin_serializer.fields['startpage_featured'].read_only is False
