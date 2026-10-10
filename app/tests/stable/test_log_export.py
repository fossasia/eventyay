"""
Tests for log CSV export functionality.
"""
import csv
import io
import pytest
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from eventyay.base.models import LogEntry
from eventyay.base.models.event import Event
from eventyay.base.models.organizer import Organizer
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestEventLogExport:
    """Test event log CSV export."""

    def test_event_log_export_requires_auth(self, client, organizer, event):
        """Test that event log export requires authentication."""
        url = reverse('control:event.log', kwargs={'organizer': organizer.slug, 'event': event.slug})
        response = client.get(f'{url}?download=yes')
        assert response.status_code == 302

    def test_event_log_export_with_permission(self, organizer_client, organizer, event, team):
        """Test event log export works for users with permission."""
        team.can_change_event_settings = True
        team.save()

        # Create some log entries
        event_ct = ContentType.objects.get_for_model(Event)
        LogEntry.objects.create(
            event=event,
            content_type=event_ct,
            object_id=event.pk,
            action_type='eventyay.event.created',
            data='{}',
        )
        LogEntry.objects.create(
            event=event,
            content_type=event_ct,
            object_id=event.pk,
            action_type='eventyay.event.changed',
            data='{"name": "new name"}',
        )

        url = reverse('control:event.log', kwargs={'organizer': organizer.slug, 'event': event.slug})
        response = organizer_client.get(f'{url}?download=yes')

        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert 'attachment' in response['Content-Disposition']
        assert f'event-logs-{event.slug}.csv' in response['Content-Disposition']

        # Parse CSV and verify content
        content = response.content.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Should have header + 2 data rows
        assert len(rows) == 3
        assert rows[0] == [
            'Date/time', 'User', 'API token', 'Device', 'OAuth application',
            'Action type', 'Object', 'Description', 'Data', 'Shredded'
        ]

    def test_event_log_export_filters_by_user(self, organizer_client, organizer, event, team, user):
        """Test event log export respects user filter."""
        team.can_change_event_settings = True
        team.save()

        event_ct = ContentType.objects.get_for_model(Event)
        # Create log entries with different users
        LogEntry.objects.create(
            event=event,
            content_type=event_ct,
            object_id=event.pk,
            user=user,
            action_type='eventyay.event.created',
            data='{}',
        )
        LogEntry.objects.create(
            event=event,
            content_type=event_ct,
            object_id=event.pk,
            action_type='eventyay.event.changed',
            data='{}',
        )

        url = reverse('control:event.log', kwargs={'organizer': organizer.slug, 'event': event.slug})
        response = organizer_client.get(f'{url}?download=yes&user=yes')

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Should have header + 1 data row (only user actions)
        assert len(rows) == 2

    def test_event_log_export_empty_result(self, organizer_client, organizer, event, team):
        """Test event log export with empty result set."""
        team.can_change_event_settings = True
        team.save()

        url = reverse('control:event.log', kwargs={'organizer': organizer.slug, 'event': event.slug})
        response = organizer_client.get(f'{url}?download=yes')

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        # Should have only header row
        assert len(rows) == 1
        assert rows[0] == [
            'Date/time', 'User', 'API token', 'Device', 'OAuth application',
            'Action type', 'Object', 'Description', 'Data', 'Shredded'
        ]

    def test_event_log_export_sanitizes_sensitive_data(self, organizer_client, organizer, event, team):
        """Test that sensitive data in log entries is redacted."""
        team.can_change_event_settings = True
        team.save()

        event_ct = ContentType.objects.get_for_model(Event)
        LogEntry.objects.create(
            event=event,
            content_type=event_ct,
            object_id=event.pk,
            action_type='eventyay.test.action',
            data='{"password": "secret123", "api_key": "key123", "normal_field": "value"}',
        )

        url = reverse('control:event.log', kwargs={'organizer': organizer.slug, 'event': event.slug})
        response = organizer_client.get(f'{url}?download=yes')

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert '[REDACTED]' in content
        assert 'secret123' not in content
        assert 'key123' not in content
        assert 'value' in content


@pytest.mark.django_db
class TestOrganizerLogExport:
    """Test organizer log CSV export."""

    def test_organizer_log_export_requires_auth(self, client, organizer):
        """Test that organizer log export requires authentication."""
        url = reverse('control:organizer.log', kwargs={'organizer': organizer.slug})
        response = client.get(f'{url}?download=yes')
        assert response.status_code == 302

    def test_organizer_log_export_with_permission(self, organizer_client, organizer, team):
        """Test organizer log export works for users with permission."""
        team.can_change_organizer_settings = True
        team.save()

        # Create an event and some log entries linked to organizer
        event = Event.objects.create(
            organizer=organizer,
            name='Test Event',
            slug='testevent',
            date_from=timezone.now() + timedelta(days=30),
            date_to=timezone.now() + timedelta(days=32),
            currency='USD',
            locale='en',
        )

        organizer_ct = ContentType.objects.get_for_model(Organizer)
        LogEntry.objects.create(
            event=event,
            content_type=organizer_ct,
            object_id=organizer.pk,
            action_type='eventyay.organizer.created',
            data='{}',
        )

        url = reverse('control:organizer.log', kwargs={'organizer': organizer.slug})
        response = organizer_client.get(f'{url}?download=yes')

        assert response.status_code == 200
        assert response['Content-Type'] == 'text/csv'
        assert 'attachment' in response['Content-Disposition']
        assert f'organizer-logs-{organizer.slug}.csv' in response['Content-Disposition']

        content = response.content.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0] == [
            'Date/time', 'User', 'API token', 'Device', 'OAuth application',
            'Event', 'Action type', 'Object', 'Description', 'Data', 'Shredded'
        ]

    def test_organizer_log_export_empty_result(self, organizer_client, organizer, team):
        """Test organizer log export with empty result set."""
        team.can_change_organizer_settings = True
        team.save()

        url = reverse('control:organizer.log', kwargs={'organizer': organizer.slug})
        response = organizer_client.get(f'{url}?download=yes')

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        assert len(rows) == 1