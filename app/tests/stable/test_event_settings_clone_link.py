import pytest
from django.test import override_settings
from django.urls import reverse


def clone_url(event):
    return reverse(
        'eventyay_common:event.clone',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_event_settings_page_has_no_clone_link(organizer_client, event):
    url = reverse(
        'eventyay_common:event.update',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.get(url)
    assert response.status_code == 200
    assert clone_url(event) not in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_organizer_event_list_still_links_to_clone(organizer_client, event):
    url = reverse('control:organizer', kwargs={'organizer': event.organizer.slug})
    response = organizer_client.get(url)
    assert response.status_code == 200
    assert clone_url(event) in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_clone_page_still_loads(organizer_client, event):
    response = organizer_client.get(clone_url(event))
    assert response.status_code == 200
