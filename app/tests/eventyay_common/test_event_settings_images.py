import pytest
from django.test import override_settings
from django.urls import reverse


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    ('payload', 'setting_key'),
    [
        ({'field': 'settings-event_preview_image'}, 'event_preview_image'),
        ({'field': 'settings-logo_image', 'setting_key': 'logo_image'}, 'logo_image'),
        ({'field': 'settings-og_image'}, 'og_image'),
    ],
)
def test_ajax_delete_image_setting(organizer_client, event, payload, setting_key):
    event.settings.set(setting_key, f'file://pub/{event.organizer.slug}/{event.slug}/{setting_key}.png')
    event.settings.set(f'{setting_key}_original_ext', 'png')

    response = organizer_client.post(
        reverse('eventyay_common:event.update', kwargs={'organizer': event.organizer.slug, 'event': event.slug}),
        {'ajax': 'delete_image', **payload},
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )

    assert response.status_code == 200
    assert response.json() == {'success': True}
    event.settings.flush()
    assert event.settings.get(setting_key) is None
    assert event.settings.get(f'{setting_key}_original_ext') is None


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_ajax_delete_rejects_non_file_setting(organizer_client, event):
    response = organizer_client.post(
        reverse('eventyay_common:event.update', kwargs={'organizer': event.organizer.slug, 'event': event.slug}),
        {
            'ajax': 'delete_image',
            'field': 'settings-primary_color',
            'setting_key': 'primary_color',
        },
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
    )

    assert response.status_code == 400
    assert response.json() == {'success': False, 'error': 'Invalid field'}


@pytest.mark.django_db
def test_resolve_media_path_path_traversal():
    from eventyay.common.text.path import resolve_media_path

    # Test path traversal containment
    assert resolve_media_path('../../etc/passwd') is None
    assert resolve_media_path('pub/../../etc/passwd') is None
    assert resolve_media_path('pub/events/../../../etc/passwd') is None
    # Test valid paths
    assert resolve_media_path('pub/events/../../passwd') == 'passwd'
    assert resolve_media_path('pub/events/myimage.png') == 'pub/events/myimage.png'
    assert resolve_media_path('file://pub/events/myimage.png') == 'pub/events/myimage.png'
    # Test absolute URL pass-through
    assert resolve_media_path('https://example.com/logo.png') == 'https://example.com/logo.png'




