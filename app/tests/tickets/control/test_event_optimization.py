import pytest
from django.test import TestCase, override_settings
from django.db import connection, reset_queries

from eventyay.base.models import Event, Organizer
from eventyay.control.views.admin_views import EventList, EventAdminToken, EventClear


@override_settings(DEBUG=True)
class EventQuerysetOptimizationTest(TestCase):
    """Test that Event queries use select_related to prevent N+1 query issues"""
    
    def setUp(self):
        """Create test data: 1 organizer and 10 events"""
        self.organizer = Organizer.objects.create(
            name="Test Organizer",
            slug="test-org"
        )
        
        # Create 10 test events
        self.events = []
        for i in range(10):
            event = Event.objects.create(
                organizer=self.organizer,
                name=f"Test Event {i}",
                slug=f"test-event-{i}",
                date_from="2026-01-01 10:00:00",
                date_to="2026-01-01 18:00:00",
                currency="USD"
            )
            self.events.append(event)
    
    def test_event_list_uses_select_related(self):
        """
        Test that EventList view uses select_related('organizer')
        to prevent N+1 queries when accessing event.organizer
        """
        # Get queryset from EventList view
        view = EventList()
        queryset = view.get_queryset()
        
        # Reset query log
        reset_queries()
        
        # Fetch events and access organizer (triggers queries)
        events = list(queryset[:10])
        for event in events:
            _ = event.organizer.name  # This would cause N+1 without select_related
        
        # Count total queries
        query_count = len(connection.queries)
        
        # ASSERTION: With select_related, should be 1-2 queries max
        # Without select_related, would be 11 queries (1 for events + 10 for organizers)
        self.assertLessEqual(
            query_count,
            2,
            f"Expected max 2 queries with select_related, got {query_count}. "
            f"Possible N+1 query issue!"
        )
    
    def test_event_admin_token_uses_select_related(self):
        """
        Test that EventAdminToken view uses select_related('organizer')
        """
        # Get queryset from EventAdminToken view
        view = EventAdminToken()
        queryset = view.get_queryset()
        
        # Reset query log
        reset_queries()
        
        # Fetch events and access organizer
        events = list(queryset[:10])
        for event in events:
            _ = event.organizer.slug
        
        # Count queries
        query_count = len(connection.queries)
        
        # Should be optimized with select_related
        self.assertLessEqual(
            query_count,
            2,
            f"Expected max 2 queries, got {query_count}. N+1 issue in EventAdminToken!"
        )
    
    def test_event_clear_uses_select_related(self):
        """
        Test that EventClear view uses select_related('organizer')
        """
        # Get queryset from EventClear view
        view = EventClear()
        queryset = view.get_queryset()
        
        # Reset query log
        reset_queries()
        
        # Fetch events and access organizer
        events = list(queryset[:10])
        for event in events:
            _ = event.organizer.name
        
        # Count queries
        query_count = len(connection.queries)
        
        # Should be optimized
        self.assertLessEqual(
            query_count,
            2,
            f"Expected max 2 queries, got {query_count}. N+1 issue in EventClear!"
        )
    
    def test_n1_query_would_occur_without_select_related(self):
        """
        Demonstrate that WITHOUT select_related, N+1 queries occur.
        This test intentionally uses the inefficient pattern to prove the problem.
        """
        # Query WITHOUT select_related (the old, broken way)
        queryset = Event.objects.all()  # NO select_related!
        
        # Reset query log
        reset_queries()
        
        # Fetch events and access organizer
        events = list(queryset[:10])
        for event in events:
            _ = event.organizer.name  # This triggers N+1!
        
        # Count queries
        query_count = len(connection.queries)
        
        # WITHOUT select_related, we expect 11 queries (1 + 10)
        # This demonstrates the problem we fixed
        self.assertGreaterEqual(
            query_count,
            11,
            f"Expected 11+ queries without select_related (demonstrating N+1), "
            f"but got {query_count}. This test proves the problem exists."
        )
