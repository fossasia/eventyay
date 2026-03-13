from datetime import datetime

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from eventyay.base.models import Event, Organizer
from eventyay.control.views.admin_views import (
    EventAdminToken,
    EventClear,
    EventList,
    EventUpdate,
)


class EventQuerysetOptimizationTest(TestCase):
    """Test that Event queries use select_related to prevent N+1 query issues"""

    def setUp(self):
        """Create test data: 1 organizer and 10 events"""
        self.organizer = Organizer.objects.create(
            name="Test Organizer",
            slug="test-org",
        )

        # Create 10 test events
        self.events = []
        for i in range(10):
            event = Event.objects.create(
                organizer=self.organizer,
                name=f"Test Event {i}",
                slug=f"test-event-{i}",
                date_from=timezone.make_aware(datetime(2026, 1, 1, 10, 0, 0)),
                date_to=timezone.make_aware(datetime(2026, 1, 1, 18, 0, 0)),
                currency="USD",
            )
            self.events.append(event)

    def _assert_no_n1_queries(self, queryset, max_queries, access_organizer_list=True):
        """
        Helper to verify that accessing organizer on queryset results
        does not cause N+1 queries.

        Args:
            queryset: The queryset to evaluate
            max_queries: Maximum expected query count (with select_related)
            access_organizer_list: If True, iterate multiple events; if False, fetch single event
        """
        with CaptureQueriesContext(connection) as context:
            if access_organizer_list:
                events = list(queryset[:10])
                for event in events:
                    _ = event.organizer.name
            else:
                event = queryset.first()
                _ = event.organizer.slug

        self.assertLessEqual(
            len(context),
            max_queries,
            f"Expected at most {max_queries} queries with select_related, "
            f"got {len(context)}. Possible N+1 query issue!\n"
            f"Queries executed:\n"
            + "\n".join(f"  {i+1}. {q['sql'][:120]}" for i, q in enumerate(context)),
        )

    def test_event_list_uses_select_related(self):
        """
        Test that EventList view uses select_related('organizer')
        to prevent N+1 queries when accessing event.organizer.
        EventList also uses prefetch_related and annotations,
        so we allow up to 3 queries total.
        """
        view = EventList()
        queryset = view.get_queryset()
        # 1 query for events (with JOIN on organizer) + 1 for prefetch_related
        # + possible annotation overhead = max 3 queries
        self._assert_no_n1_queries(queryset, max_queries=3)

    def test_event_update_uses_select_related(self):
        """
        Test that EventUpdate view uses select_related('organizer').
        EventUpdate is a FormView (UpdateView) for editing events.
        """
        view = EventUpdate()
        queryset = view.get_queryset()
        # Simple select_related query = max 2
        self._assert_no_n1_queries(queryset, max_queries=2)

    def test_event_admin_token_uses_select_related(self):
        """
        Test that EventAdminToken view uses select_related('organizer')
        when fetching a single event via its queryset.
        EventAdminToken is a DetailView, so we test single-object fetch pattern.
        """
        view = EventAdminToken()
        queryset = view.get_queryset()
        # Single object with select_related = 1 query (JOIN)
        self._assert_no_n1_queries(queryset, max_queries=1, access_organizer_list=False)

    def test_event_clear_uses_select_related(self):
        """
        Test that EventClear view uses select_related('organizer') on its queryset.
        EventClear is a DetailView and fetches a single object via get_object(),
        so we test the single-object fetch pattern.
        """
        view = EventClear()
        queryset = view.get_queryset()
        # Single object with select_related = 1 query (JOIN)
        self._assert_no_n1_queries(queryset, max_queries=1, access_organizer_list=False)
