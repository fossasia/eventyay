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
def test_user_cannot_view_talks_when_unpublished_and_no_private_mode(fresh_event, user):
    """A fresh event hides talks from the public until the organiser publishes."""
    assert fresh_event.talks_published is False
    assert fresh_event.user_can_view_talks(user=user) is False


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_orga_live_page_renders(organizer_client, event):
    """The orga talk-specific status page renders successfully."""
    orga_url = reverse('orga:event.live', kwargs={'event': event.slug})
    response = organizer_client.get(orga_url)
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_orga_private_testmode_talks_stays_on_orga_page(organizer_client, event):
    """After toggling private test mode for talks on the orga page, stay on the orga page."""
    event.private_testmode = True
    event.settings.set('private_testmode_talks', True)
    event.save()

    orga_url = reverse('orga:event.live', kwargs={'event': event.slug})
    response = organizer_client.post(
        orga_url, {'private_testmode_talks_action': 'disable'}
    )
    assert response.status_code in {301, 302}
    assert response.headers['Location'].endswith(orga_url)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_central_status_disables_private_testmode_redirect(organizer_client, event):
    """After disabling private test mode for talks, redirect goes to central page."""
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
