import pytest
from django.urls import reverse
from django.test import override_settings

@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_publication_settings_rendered_in_main_settings(organizer_client, organizer, event):
    """Test that the new Publication settings fields are rendered on the main event settings page."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })
    response = organizer_client.get(url)
    assert response.status_code == 200
    assert b"Publication" in response.content
    assert b"is_public" in response.content
    assert b"startpage_visible" in response.content
    assert b"meta_noindex" in response.content

@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_publication_settings_save_via_main_settings(organizer_client, organizer, event):
    """Test that saving settings on the main settings page updates the publication controls."""
    url = reverse('eventyay_common:event.update', kwargs={
        'organizer': organizer.slug,
        'event': event.slug
    })
    
    response = organizer_client.get(url)
    form = response.context['form']
    sform = response.context['sform']
    
    # Assert initial choices are present
    assert 'en' in sform.initial.get('locales', [])
    assert len(sform.fields['locales'].choices) > 0

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
            post_data['startpage_visible'] = 'on'
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
    assert event.startpage_visible is True
    assert event.settings.meta_noindex is True
