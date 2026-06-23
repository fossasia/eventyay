from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from eventyay.base.models import Event


@pytest.fixture
def fresh_event(db, organizer):
    """Create an event the same way an unsaved instance would default."""
    now = timezone.now()
    return Event.objects.create(
        organizer=organizer,
        name='Fresh Event',
        slug='freshevent',
        date_from=now + timedelta(days=30),
        date_to=now + timedelta(days=32),
        currency='USD',
        locale='en',
    )


@pytest.mark.django_db
def test_event_default_private_testmode_disabled(fresh_event):
    """The model field should default to disabled private test mode."""
    assert fresh_event.private_testmode is False


@pytest.mark.django_db
def test_set_defaults_does_not_enable_private_testmode(fresh_event):
    """``set_defaults`` should not enable private test mode for tickets/talks."""
    fresh_event.set_defaults()
    assert fresh_event.settings.get('private_testmode_tickets', as_type=bool) is False
    assert fresh_event.settings.get('private_testmode_talks', as_type=bool) is False
    assert fresh_event.private_testmode_tickets_enabled is False
    assert fresh_event.private_testmode_talks_enabled is False


@pytest.mark.django_db
def test_event_creation_path_private_testmode_disabled(fresh_event):
    """Simulate the view creation path: set field to False then call set_defaults().

    This covers the explicit assignment in EventCreateView.create_event()
    followed by the set_defaults() call that configures settings.
    """
    fresh_event.private_testmode = False
    fresh_event.save()
    fresh_event.set_defaults()

    fresh_event.refresh_from_db()
    assert fresh_event.private_testmode is False
    assert fresh_event.settings.get('private_testmode_tickets', as_type=bool) is False
    assert fresh_event.settings.get('private_testmode_talks', as_type=bool) is False
    assert fresh_event.private_testmode_tickets_enabled is False
    assert fresh_event.private_testmode_talks_enabled is False
    assert fresh_event.user_can_view_talks() is False
    assert fresh_event.user_can_view_tickets() is False


@pytest.mark.django_db
def test_user_cannot_view_talks_when_unpublished_and_no_private_mode(fresh_event, user):
    """A fresh event hides talks from the public until the organiser publishes."""
    assert fresh_event.talks_published is False
    assert fresh_event.user_can_view_talks(user=user) is False


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_orga_live_url_redirects_to_central(organizer_client, event):
    """The orga talk-component status URL now redirects to the central status page."""
    orga_url = reverse('orga:event.live', kwargs={'organizer': event.organizer.slug, 'event': event.slug})
    central_url = reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.get(orga_url)
    assert response.status_code in {301, 302}
    assert response.headers['Location'].endswith(central_url)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_central_status_disables_private_testmode_redirect(organizer_client, event):
    """After disabling private test mode for talks on the central page, stay on central page."""
    event.private_testmode = True
    event.settings.set('private_testmode_talks', True)
    event.save()

    central_url = reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.post(
        central_url, {'private_testmode_talks_action': 'disable'}
    )
    assert response.status_code in {301, 302}
    assert response.headers['Location'].endswith(central_url)

    event.refresh_from_db()
    event.settings.flush()
    assert event.settings.get('private_testmode_talks', as_type=bool) is False
