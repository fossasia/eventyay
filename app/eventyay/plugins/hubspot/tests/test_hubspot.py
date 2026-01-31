"""
Tests for HubSpot plugin.
"""
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
import requests
from django.utils import timezone
from django_scopes import scope

from eventyay.base.models import Event, Order, OrderPosition, Organizer


@pytest.fixture
def organizer(db):
    """Create a test organizer."""
    return Organizer.objects.create(
        name='Test Organizer',
        slug='testorg',
    )


@pytest.fixture
def event(db, organizer):
    """Create a test event."""
    now = timezone.now()
    return Event.objects.create(
        organizer=organizer,
        name='Test Event',
        slug='testevent',
        date_from=now + timedelta(days=30),
        date_to=now + timedelta(days=32),
        currency='USD',
        locale='en',
        is_public=True,
    )


@pytest.fixture
def order(db, event):
    """Create a test order."""
    return Order.objects.create(
        event=event,
        code='TEST01',
        email='buyer@example.com',
        locale='en',
        datetime=timezone.now(),
        expires=timezone.now() + timedelta(days=3),
        total=100,
        status=Order.STATUS_PAID,
    )


@pytest.fixture
def position_with_attendee(db, order):
    """Create an order position with attendee information."""
    with scope(organizer=order.event.organizer):
        position = OrderPosition.objects.create(
            order=order,
            product=_create_test_product(order.event),
            price=50,
        )
        position.attendee_email = 'attendee@example.com'
        position.attendee_name_parts = {
            'first_name': 'John',
            'last_name': 'Doe',
        }
        position.save()
    return position


def _create_test_product(event):
    """Helper to create a test product."""
    from eventyay.base.models.product import Product
    from django_scopes import scope

    with scope(organizer=event.organizer):
        return Product.objects.create(
            event=event,
            name='Test Product',
            default_price=50,
            available_from=None,
            available_until=None,
        )


class TestHubSpotSignals:
    """Test HubSpot order_paid signal handler."""

    def test_order_paid_queues_hubspot_task(self, event, order, position_with_attendee, mocker):
        """Test that order_paid signal queues the HubSpot sync task."""
        # Arrange - Import at module level
        from eventyay.plugins.hubspot.signals import on_order_paid

        event.settings.set('plugin_hubspot_enabled', True)
        event.settings.set('plugin_hubspot_api_key', 'test-token')

        # Activate the HubSpot plugin for the event
        event.plugins = 'hubspot'
        event.save()

        # Patch the task.delay method directly to verify signal → task wiring
        delay_mock = mocker.patch(
            'eventyay.plugins.hubspot.signals.sync_attendees_to_hubspot.delay'
        )

        # Ensure order is associated with the event (required for signal check)
        order.event = event
        order.save()

        # Act - Call the receiver directly (best practice for testing signals)
        on_order_paid(sender=event, order=order)

        # Assert - verify delay was called with correct arguments
        delay_mock.assert_called_once_with(
            order_pk=order.pk,
            event_pk=event.pk,
        )

    def test_hubspot_sync_not_triggered_when_disabled(self, event, order, mocker):
        """Test that HubSpot sync is not triggered when plugin is disabled."""
        # Arrange
        from eventyay.plugins.hubspot import tasks
        from eventyay.plugins.hubspot.signals import on_order_paid

        mock_apply_async = mocker.patch.object(tasks.sync_attendees_to_hubspot, 'apply_async')

        event.settings.set('plugin_hubspot_enabled', False)
        event.settings.set('plugin_hubspot_api_key', 'test-token')

        # Act - Call the receiver directly
        on_order_paid(sender=event, order=order)

        # Assert
        mock_apply_async.assert_not_called()

    def test_hubspot_sync_not_triggered_when_no_api_key(self, event, order, mocker):
        """Test that HubSpot sync is not triggered when API key is missing."""
        # Arrange
        from eventyay.plugins.hubspot import tasks
        from eventyay.plugins.hubspot.signals import on_order_paid

        mock_apply_async = mocker.patch.object(tasks.sync_attendees_to_hubspot, 'apply_async')

        event.settings.set('plugin_hubspot_enabled', True)
        # Don't set API key

        # Act - Call the receiver directly
        on_order_paid(sender=event, order=order)

        # Assert
        mock_apply_async.assert_not_called()


class TestHubSpotPayloadMapping:
    """Test HubSpot contact payload mapping."""

    def test_hubspot_payload_mapping(self, event, order, position_with_attendee, mocker):
        """Test that attendee data is correctly mapped to HubSpot payload."""
        # Arrange
        from eventyay.plugins.hubspot.tasks import sync_attendees_to_hubspot

        event.settings.set('plugin_hubspot_enabled', True)
        event.settings.set('plugin_hubspot_api_key', 'test-token')

        mock_post = mocker.patch('eventyay.plugins.hubspot.tasks.requests.post')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [
                {'id': 'attendee@example.com', 'properties': {}}
            ],
            'errors': [],
        }
        mock_post.return_value = mock_response

        # Act
        sync_attendees_to_hubspot(order.pk, event.pk)

        # Assert - verify request was made with correct contact data
        assert mock_post.called
        call_args = mock_post.call_args
        payload = call_args.kwargs['json']

        # Verify payload structure has inputs array with at least one contact
        assert 'inputs' in payload
        assert len(payload['inputs']) >= 1

        # Find the contact by email in the inputs (id field is derived, not essential)
        contact = payload['inputs'][0]
        assert contact['properties']['email'] == 'attendee@example.com'
        assert contact['properties']['firstname'] == 'John'
        assert contact['properties']['lastname'] == 'Doe'

    def test_hubspot_skips_positions_without_email(self, event, order, mocker):
        """Test that positions without attendee email are skipped."""
        # Arrange
        from eventyay.plugins.hubspot.tasks import sync_attendees_to_hubspot

        event.settings.set('plugin_hubspot_enabled', True)
        event.settings.set('plugin_hubspot_api_key', 'test-token')

        # Create a position without attendee email
        with scope(organizer=event.organizer):
            position = OrderPosition.objects.create(
                order=order,
                product=_create_test_product(event),
                price=50,
            )
            # No attendee_email set

        mock_post = mocker.patch('eventyay.plugins.hubspot.tasks.requests.post')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'results': [],
            'errors': [],
        }
        mock_post.return_value = mock_response

        # Act
        sync_attendees_to_hubspot(order.pk, event.pk)

        # Assert
        # Should not call the API if there are no contacts to sync
        assert not mock_post.called

    def test_hubspot_handles_api_errors(self, event, order, position_with_attendee, mocker):
        """Test that API errors are surfaced to the caller."""
        # Arrange
        from eventyay.plugins.hubspot.tasks import sync_attendees_to_hubspot

        event.settings.set('plugin_hubspot_enabled', True)
        event.settings.set('plugin_hubspot_api_key', 'test-token')

        # Mock requests.post to raise an exception
        mocker.patch(
            'eventyay.plugins.hubspot.tasks.requests.post',
            side_effect=requests.RequestException('API Error'),
        )

        # Act & Assert - task should raise the original exception in synchronous execution
        with pytest.raises(requests.RequestException):
            sync_attendees_to_hubspot(order.pk, event.pk)

