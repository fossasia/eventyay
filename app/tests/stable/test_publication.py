import pytest
import re
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
    
    # Assert initial choices are present (replacing prints)
    assert 'en' in sform.initial.get('locales', [])
    assert len(sform.fields['locales'].choices) > 0
    
    def construct_post_data(enable_publication=True):
        post_data = {
            'settings-timezone': 'UTC',
            'settings-locale': 'en',
            'settings-locales': sform.initial.get('locales') or ['en'],
            'is_public': 'on' if enable_publication else '',
            'startpage_visible': 'on' if enable_publication else '',
            'settings-meta_noindex': 'on' if enable_publication else '',
            
            # Form required fields (I18n/SplitDateTime fields require _0, _1 suffixes)
            'name_0': 'Test Event',
            'date_from_0': '2026-10-01',
            'date_from_1': '10:00:00',
            'date_to_0': '2026-10-02',
            'date_to_1': '18:00:00',
        }
        
        # Add required form values from context
        import i18nfield.forms
        from django import forms
        
        def populate_from_form(form_obj, prefix_str=''):
            for name, field in form_obj.fields.items():
                initial = form_obj.initial.get(name)
                key = f"{prefix_str}{name}"
                
                if key in post_data:
                    continue
                    
                if isinstance(field, i18nfield.forms.I18nFormField):
                    val = initial.data if hasattr(initial, 'data') else initial
                    if isinstance(val, dict):
                        post_data[f"{key}_0"] = str(val.get('en', val.get(list(val.keys())[0], '')) if val else 'Test')
                    else:
                        post_data[f"{key}_0"] = str(val or 'Test')
                elif isinstance(field, forms.SplitDateTimeField):
                    post_data[f"{key}_0"] = '2026-10-01' if 'from' in key else '2026-10-02'
                    post_data[f"{key}_1"] = '10:00:00' if 'from' in key else '18:00:00'
                elif isinstance(field, (forms.FileField, forms.ImageField)):
                    # Browsers don't submit text for empty file inputs
                    continue
                else:
                    if initial is not None:
                        if isinstance(initial, (list, tuple)) and not initial:
                            post_data[key] = ''
                        elif hasattr(initial, 'strftime'):
                            post_data[key] = initial.strftime('%Y-%m-%d %H:%M:%S')
                        else:
                            post_data[key] = str(initial)

        populate_from_form(form, '')
        populate_from_form(sform, 'settings-')

        # Include formset management fields from context
        if 'plugin_formset' in response.context:
            for key, val in response.context['plugin_formset'].management_form.initial.items():
                post_data[f"{response.context['plugin_formset'].prefix}-{key}"] = str(val)
                
        return post_data
        
    # Enable all settings
    post_data_enable = construct_post_data(enable_publication=True)
    response = organizer_client.post(url, post_data_enable, follow=True)
    
    if response.status_code == 200 and not response.redirect_chain:
        form = response.context['form']
        sform = response.context['sform']
        assert not form.errors, f"Form failed with errors: {form.errors}"
        assert not sform.errors, f"Settings form failed with errors: {sform.errors}"
        
    assert response.status_code == 200
    assert len(response.redirect_chain) > 0, "Enable form submission did not redirect"
    
    event.refresh_from_db()
    event.settings.flush()
    assert event.is_public is True
    assert event.startpage_visible is True
    assert event.settings.meta_noindex is True
