from datetime import datetime

from django.conf import settings
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from eventyay.base.models import BBBServer, Event, JanusServer, Organizer, TurnServer, User
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
        self.request_factory = RequestFactory()
        self.staff_user = User.objects.create_user(
            "staff@example.com",
            "secret",
            is_staff=True,
            fullname="Staff User",
        )

    def _configured_event(self):
        event = self.events[0]
        event.config = {
            "JWT_secrets": [
                {
                    "issuer": "any",
                    "audience": "eventyay",
                    "secret": "this-is-a-test-secret-with-more-than-thirty-two-chars",
                }
            ]
        }
        event.save(update_fields=["config"])
        return event

    def _call_admin_token_view(self, event):
        request = self.request_factory.get("/admin/video/events/token/")
        request.user = self.staff_user
        view = EventAdminToken()
        view.request = request
        view.kwargs = {"pk": str(event.pk)}
        return view.get(request)

    def _assert_no_n1_queries(self, queryset, relation_attr="organizer", attr_prop="slug", fetch_all=False):
        """
        Helper to verify that accessing related fields on queryset results
        does not cause N+1 queries and that select_related is configured
        for the expected relation.
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

        # Verify select_related for the specific relation, avoiding generic JOIN checks.
        select_related_map = getattr(queryset.query, "select_related", None)
        if select_related_map is True:
            return
        if isinstance(select_related_map, dict):
            self.assertIn(
                relation_attr,
                select_related_map,
                f"Expected queryset to select_related('{relation_attr}'), but it was not configured.",
            )
            return
        self.fail(
            f"Expected queryset to use select_related for '{relation_attr}', "
            f"but select_related is {select_related_map!r}."
        )

    def test_event_update_uses_select_related(self):
        view = EventUpdate()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, fetch_all=True)

    def test_event_admin_token_uses_select_related(self):
        view = EventAdminToken()
        queryset = view.get_queryset()
        self._assert_no_n1_queries(queryset, fetch_all=False)

    def test_event_admin_token_preserves_domain_path(self):
        event = self._configured_event()
        event.domain = "example.com/myapp"
        event.save(update_fields=["domain"])

        response = self._call_admin_token_view(event)

        assert response.status_code == 302
        assert response["Location"].startswith("https://example.com/myapp#token=")

    def test_event_admin_token_invalid_domain_falls_back_to_request_host(self):
        event = self._configured_event()
        event.domain = "https://evil.example.com/path"
        event.save(update_fields=["domain"])

        response = self._call_admin_token_view(event)

        expected_scheme = "https" if not settings.DEBUG else "http"
        assert response.status_code == 302
        assert response["Location"].startswith(
            f"{expected_scheme}://testserver{event.urls.video_base}#token="
        )

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
