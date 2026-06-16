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
    names = re.findall(r'name=["\']([^"\']+)["\']', response.content.decode('utf-8'))
    
    form = response.context['form']
    sform = response.context['sform']
    
    print("SFORM LOCALES INITIAL:", sform.initial.get('locales'))
    print("SFORM LOCALES CHOICES:", list(sform.fields['locales'].choices))
    
    def construct_post_data(enable_publication=True):
        post_data = {
            'settings-timezone': 'UTC',
            'settings-locale': 'en',
            'settings-locales': sform.initial.get('locales') or ['en'],
        }
        
        for name in names:
            if name == 'csrfmiddlewaretoken':
                continue
            
            # 1. Formset management fields
            if 'TOTAL_FORMS' in name or 'INITIAL_FORMS' in name:
                post_data[name] = '0'
                continue
            elif 'MIN_NUM_FORMS' in name:
                post_data[name] = '0'
                continue
            elif 'MAX_NUM_FORMS' in name:
                post_data[name] = '1000'
                continue
                
            # 2. Publication settings (the fields we want to test)
            if name == 'is_public':
                if enable_publication:
                    post_data[name] = 'on'
                continue
            elif name == 'startpage_visible':
                if enable_publication:
                    post_data[name] = 'on'
                continue
            elif name == 'settings-meta_noindex':
                if enable_publication:
                    post_data[name] = 'on'
                continue
                
            # 3. Settings fields (sform)
            if name.startswith('settings-'):
                field_key = name[len('settings-'):]
                if field_key == 'locales' or field_key == 'locale':
                    continue
                # If it ends with _0 (localized setting field)
                if field_key.endswith('_0'):
                    field_key = field_key[:-2]
                val = sform.initial.get(field_key)
                if val is not None:
                    post_data[name] = str(val)
                continue
                
            # 4. Standard/multilingual form fields
            base_name = name
            if name.endswith('_0'):
                base_name = name[:-2]
            
            val = form.initial.get(base_name)
            if val is not None:
                if name.endswith('_0'):
                    post_data[name] = str(val)
                elif 'date' in name:
                    if name.endswith('_0'):
                        post_data[name] = val.strftime('%Y-%m-%d')
                    elif name.endswith('_1'):
                        post_data[name] = val.strftime('%H:%M:%S')
                else:
                    post_data[name] = val
            else:
                if base_name == 'name':
                    post_data[name] = 'Test Event'
                elif base_name == 'email':
                    post_data[name] = 'test@example.com'
                elif name == 'date_from_0':
                    post_data[name] = event.date_from.strftime('%Y-%m-%d')
                elif name == 'date_from_1':
                    post_data[name] = event.date_from.strftime('%H:%M:%S')
                    
        return post_data
        
    # Enable all settings
    post_data_enable = construct_post_data(enable_publication=True)
    response = organizer_client.post(url, post_data_enable, follow=True)
    
    if response.status_code == 200 and not response.redirect_chain:
        form = response.context['form']
        sform = response.context['sform']
        print("ENABLE FORM ERRORS:", form.errors)
        print("ENABLE SFORM ERRORS:", sform.errors)
        
    assert response.status_code == 200
    assert len(response.redirect_chain) > 0, "Enable form submission did not redirect"
    
    event.refresh_from_db()
    event.settings.flush()
    assert event.is_public is True
    assert event.startpage_visible is True
    assert event.settings.meta_noindex is True
