from datetime import datetime

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from eventyay.base.models import BBBServer, Event, JanusServer, Organizer, TurnServer
from eventyay.control.views.admin_views import (
    BBBServerList,
    EventAdminToken,
    EventClear,
    EventList,
    EventUpdate,
    JanusServerList,
    TurnServerList,
)


class EventQuerysetOptimizationTest(TestCase):
    """
    Test that Event queries use select_related to prevent N+1 query issues.
    Note: CaptureQueriesContext monitors synchronous SQL generation,
    so async ORM executions (if introduced) will require pytest-asyncio query testing.
    """

    def setUp(self):
        """Create test data: 1 organizer and 10 events, plus auxiliary servers"""
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

        # Create server instances linked to the first event
        self.bbb = BBBServer.objects.create(
            url="https://bbb.example.com",
            secret="some-secret",
            event_exclusive=self.events[0],
        )
        self.janus = JanusServer.objects.create(
            url="https://janus.example.com",
            room_create_key="some-secret",
            event_exclusive=self.events[0],
        )
        self.turn = TurnServer.objects.create(
            hostname="turn.example.com",
            auth_secret="some-secret",
            event_exclusive=self.events[0],
        )

    def _assert_no_n1_queries(self, queryset, relation_attr="organizer", attr_prop="slug", fetch_all=False):
        """
        Helper to verify that accessing related fields on queryset results
        does not cause N+1 queries by asserting an explicit SQL JOIN exists.
        """
        with CaptureQueriesContext(connection) as context:
            if fetch_all:
                objects = list(queryset[:10])
                for obj in objects:
                    related_obj = getattr(obj, relation_attr)
                    if related_obj:
                        _ = getattr(related_obj, attr_prop)
            else:
                obj = queryset.first()
                if obj:
                    related_obj = getattr(obj, relation_attr)
                    if related_obj:
                        _ = getattr(related_obj, attr_prop)

        # Allow some tolerance for schema joins, but strictly enforce no loop scaling.
        # A true N+1 would trigger > 10 queries here safely throwing.
        self.assertLessEqual(
            len(context),
            4,
            f"Expected constant bounded queries, got {len(context)}. Possible N+1 issue!",
        )

        # Issue 9: Enforce a structural JOIN to prove select_related is working
        if len(context) > 0:
            sql_log = "\n".join(q["sql"].upper() for q in context)
            self.assertIn(" JOIN ", sql_log, f"Validation failure: No SQL JOIN generated for {relation_attr}.")

    def test_event_update_uses_select_related(self):
        view = EventUpdate()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, fetch_all=True)

    def test_event_admin_token_uses_select_related(self):
        view = EventAdminToken()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, fetch_all=False)

    def test_event_clear_uses_select_related(self):
        view = EventClear()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, fetch_all=False)

    def test_event_list_uses_select_related(self):
        view = EventList()
        # EventList has heavy subqueries, but select_related must still be active.
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, fetch_all=True)

    def test_bbb_server_uses_select_related(self):
        view = BBBServerList()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, relation_attr="event_exclusive", fetch_all=True)

    def test_janus_server_uses_select_related(self):
        view = JanusServerList()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, relation_attr="event_exclusive", fetch_all=True)

    def test_turn_server_uses_select_related(self):
        view = TurnServerList()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, relation_attr="event_exclusive", fetch_all=True)
