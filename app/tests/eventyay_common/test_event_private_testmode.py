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
def test_central_status_talk_mode_public_blocked_when_unpublished(organizer_client, event):
    """Talks cannot be published if the event main page is not live."""
    event.live = False
    event.save()
    central_url = reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.post(central_url, {'talk_mode': 'public'})
    assert response.status_code in {301, 302}
    event.refresh_from_db()
    assert event.talks_published is False


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_central_status_talk_mode_public(organizer_client, event):
    """Talks can be published if the event main page is live."""
    event.live = True
    event.save()
    central_url = reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.post(central_url, {'talk_mode': 'public'})
    assert response.status_code in {301, 302}
    event.refresh_from_db()
    assert event.talks_published is True
    assert event.settings.get('private_testmode_talks', default=False, as_type=bool) is False


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_central_status_ticketing_mode_public_test_blocked_when_unpublished(organizer_client, event):
    """Public test mode cannot be enabled if event is not live."""
    event.live = False
    event.save()
    from eventyay.base.models import Product, Quota
    product = Product.objects.create(event=event, name="Ticket", default_price=10)
    quota = Quota.objects.create(event=event, name="Quota", size=100)
    quota.products.add(product)
    
    central_url = reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.post(central_url, {'ticketing_mode': 'public_test'})
    assert response.status_code in {301, 302}
    event.refresh_from_db()
    assert event.testmode is False


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_central_status_ticketing_mode_public_sales_with_delete_test_orders(organizer_client, event):
    """Public sales can be enabled and test orders deleted."""
    event.live = True
    event.testmode = True
    event.save()
    from django_scopes import scope
    from eventyay.base.models import Product, Quota, Order
    with scope(organizer=event.organizer):
        product = Product.objects.create(event=event, name="Ticket", default_price=10)
        quota = Quota.objects.create(event=event, name="Quota", size=100)
        quota.products.add(product)

        Order.objects.create(event=event, status=Order.STATUS_PENDING, testmode=True, expires=timezone.now(), total=0)
        Order.objects.create(event=event, status=Order.STATUS_PENDING, testmode=False, expires=timezone.now(), total=0)

    central_url = reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.post(central_url, {'ticketing_mode': 'public_sales', 'delete_test_orders': 'yes'})
    assert response.status_code in {301, 302}
    event.refresh_from_db()
    assert event.tickets_published is True
    assert event.testmode is False
    with scope(organizer=event.organizer):
        assert Order.objects.filter(event=event, testmode=True).count() == 0
        assert Order.objects.filter(event=event, testmode=False).count() == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_central_status_ticketing_mode_public_sales_without_delete_test_orders(organizer_client, event):
    """Public sales can be enabled and test orders retained."""
    event.live = True
    event.testmode = True
    event.save()
    from django_scopes import scope
    from eventyay.base.models import Product, Quota, Order
    with scope(organizer=event.organizer):
        product = Product.objects.create(event=event, name="Ticket", default_price=10)
        quota = Quota.objects.create(event=event, name="Quota", size=100)
        quota.products.add(product)

        Order.objects.create(event=event, status=Order.STATUS_PENDING, testmode=True, expires=timezone.now(), total=0)

    central_url = reverse(
        'eventyay_common:event.live',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    response = organizer_client.post(central_url, {'ticketing_mode': 'public_sales'})
    assert response.status_code in {301, 302}
    event.refresh_from_db()
    assert event.tickets_published is True
    assert event.testmode is False
    with scope(organizer=event.organizer):
        assert Order.objects.filter(event=event, testmode=True).count() == 1