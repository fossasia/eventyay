import pytest
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    ('payload', 'setting_key'),
    [
        ({'field': 'settings-organizer_logo_image'}, 'organizer_logo_image'),
        ({'field': 'settings-organizer_header_image', 'setting_key': 'organizer_header_image'}, 'organizer_header_image'),
    ],
)
def test_ajax_delete_organizer_image_setting(organizer_client, organizer, payload, setting_key):
    organizer.settings.set(setting_key, f'file://pub/{organizer.slug}/{setting_key}.png')
    organizer.settings.set(f'{setting_key}_original_ext', 'png')

    response = organizer_client.post(
        reverse('eventyay_common:organizer.edit', kwargs={'organizer': organizer.slug}),
        {'ajax': 'delete_image', **payload},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )

    assert response.status_code == 200
    assert response.json() == {'success': True}
    organizer.settings.flush()
    assert organizer.settings.get(setting_key) is None
    assert organizer.settings.get(f'{setting_key}_original_ext') is None


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_ajax_delete_organizer_rejects_non_file_setting(organizer_client, organizer):
    response = organizer_client.post(
        reverse('eventyay_common:organizer.edit', kwargs={'organizer': organizer.slug}),
        {
            'ajax': 'delete_image',
            'field': 'settings-primary_color',
            'setting_key': 'primary_color',
        },
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )

    assert response.status_code == 400
    assert response.json() == {'success': False, 'error': 'Invalid field'}
