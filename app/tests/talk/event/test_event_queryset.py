from django.test import TestCase
from django.utils.timezone import now, timedelta

from eventyay.base.models.event import Event
from eventyay.base.models.organizer import Organizer
from eventyay.base.models.cfp import CfP
from eventyay.base.models.type import SubmissionType


class EventQuerySetTest(TestCase):
    """
    Tests for the visible_on_startpage() queryset method.
    
    Tests the business logic that filters events based on:
    - Being current or upcoming (NOT past)
    - Having active Tickets OR Talks components
    
    Per issue #2237: Only current and upcoming events with active 
    components should appear on the start page.
    """

    def setUp(self):
        self.organizer = Organizer.objects.create(
            name="Test Organizer",
            slug="test-org"
        )

    def create_event(self, **kwargs):
        defaults = {
            "organizer": self.organizer,
            "name": "Test Event",
            "slug": f"test-event-{now().timestamp()}",
            "live": True,
            "date_from": now(),
            "date_to": now() + timedelta(days=5),
            "tickets_published": False,
            "talks_published": False,
        }
        defaults.update(kwargs)
        return Event.objects.create(**defaults)

    def create_cfp(self, event, deadline=None, submission_deadline=None):
        """Updates the existing CfP (OneToOne with Event)"""
        cfp = event.cfp
        cfp.deadline = deadline
        cfp.save()

        if submission_deadline:
            submission_type = SubmissionType.objects.create(
                event=event,
                name="Talk",
                deadline=submission_deadline
            )
            cfp.default_type = submission_type
            cfp.save()

        return cfp

    # ===============================
    # ✅ Tickets Component - Active
    # ===============================

    def test_future_event_with_live_tickets_is_visible(self):
        """Event with active ticket sales should be visible"""
        event = self.create_event(
            tickets_published=True,
            presale_start=now() - timedelta(days=1),
            presale_end=now() + timedelta(days=2),
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    def test_ongoing_event_with_live_tickets_is_visible(self):
        """Currently happening event with active tickets should be visible"""
        event = self.create_event(
            tickets_published=True,
            presale_start=now() - timedelta(days=5),
            presale_end=now() + timedelta(days=2),
            date_from=now() - timedelta(days=1),  # Started yesterday
            date_to=now() + timedelta(days=3),    # Ends in 3 days
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    def test_event_with_tickets_published_but_presale_not_started_is_not_visible(self):
        """Event with future ticket sales should not be visible yet"""
        event = self.create_event(
            tickets_published=True,
            presale_start=now() + timedelta(days=1),  # Not started
            presale_end=now() + timedelta(days=5),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    def test_event_with_expired_ticket_sales_is_not_visible(self):
        """Event with expired ticket sales should not be visible"""
        event = self.create_event(
            tickets_published=True,
            presale_start=now() - timedelta(days=5),
            presale_end=now() - timedelta(days=1),  # Expired
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    def test_event_with_null_presale_dates_and_tickets_published_is_visible(self):
        """Event with tickets published and no presale restrictions should be visible"""
        event = self.create_event(
            tickets_published=True,
            presale_start=None,  # No restrictions
            presale_end=None,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    # ===============================
    # ✅ Talks/CFP Component - Active
    # ===============================

    def test_event_with_valid_cfp_deadline_is_visible(self):
        """Event with open CFP deadline should be visible"""
        event = self.create_event(
            talks_published=True,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        self.create_cfp(
            event,
            deadline=now() + timedelta(days=5)
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    def test_event_with_valid_submission_type_deadline_is_visible(self):
        """Event with open submission type deadline should be visible"""
        event = self.create_event(
            talks_published=True,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        self.create_cfp(
            event,
            deadline=None,  # No CFP deadline
            submission_deadline=now() + timedelta(days=5)
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    def test_event_with_null_cfp_deadline_is_visible(self):
        """Event with no CFP deadline (always open) should be visible"""
        event = self.create_event(
            talks_published=True,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        self.create_cfp(
            event,
            deadline=None  # Always open
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    def test_event_with_expired_cfp_is_not_visible(self):
        """Event with expired CFP should not be visible"""
        event = self.create_event(
            talks_published=True,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        self.create_cfp(
            event,
            deadline=now() - timedelta(days=1),  # Expired
            submission_deadline=now() - timedelta(days=1)  # Also expired
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    def test_event_with_talks_published_but_no_cfp_is_not_visible(self):
        """Event with talks_published but no CFP object should not be visible"""
        event = self.create_event(
            talks_published=True,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )
        
        # Delete the auto-created CFP
        event.cfp.delete()

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    # ===============================
    # ❌ Past Events - EXCLUDED
    # ===============================

    def test_past_event_with_active_tickets_is_not_visible(self):
        """Past events should be excluded even with active tickets (issue #2237)"""
        event = self.create_event(
            date_from=now() - timedelta(days=5),
            date_to=now() - timedelta(days=1),  # Ended yesterday
            tickets_published=True,
            presale_start=now() - timedelta(days=10),
            presale_end=now() + timedelta(days=1),  # Still active but event is past
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    def test_past_event_with_open_cfp_is_not_visible(self):
        """Past events should be excluded even with open CFP (issue #2237)"""
        event = self.create_event(
            talks_published=True,
            date_from=now() - timedelta(days=5),
            date_to=now() - timedelta(days=1),  # Ended yesterday
        )

        self.create_cfp(
            event,
            deadline=now() + timedelta(days=5)  # CFP still open but event is past
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    # ===============================
    # ❌ Not Live - EXCLUDED
    # ===============================

    def test_not_live_event_is_not_visible(self):
        """Events not marked as live should not be visible"""
        event = self.create_event(
            live=False,
            tickets_published=True,
            presale_start=now() - timedelta(days=1),
            presale_end=now() + timedelta(days=2),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    # ===============================
    # ❌ No Active Component - EXCLUDED
    # ===============================

    def test_event_without_active_component_is_not_visible(self):
        """Event with no active tickets or CFP should not be visible"""
        event = self.create_event(
            tickets_published=False,
            talks_published=False,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    def test_future_event_with_tickets_not_published_is_not_visible(self):
        """Event with tickets_published=False should not be visible"""
        event = self.create_event(
            tickets_published=False,
            presale_start=now() - timedelta(days=1),
            presale_end=now() + timedelta(days=2),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    def test_future_event_with_talks_not_published_is_not_visible(self):
        """Event with talks_published=False should not be visible"""
        event = self.create_event(
            talks_published=False,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        self.create_cfp(
            event,
            deadline=now() + timedelta(days=5)
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    # ===============================
    # ✅ Both Components Active
    # ===============================

    def test_event_with_both_components_active_is_visible(self):
        """Event with both tickets and CFP active should be visible"""
        event = self.create_event(
            tickets_published=True,
            presale_start=now() - timedelta(days=1),
            presale_end=now() + timedelta(days=2),
            talks_published=True,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        self.create_cfp(
            event,
            deadline=now() + timedelta(days=5)
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    # ===============================
    # ✅ Edge Cases
    # ===============================

    def test_event_ending_today_is_visible(self):
        """Event ending today should still be visible"""
        from django.utils import timezone
        
        today = timezone.localdate()
        current_time = timezone.now()
        
        event = self.create_event(
            tickets_published=True,
            presale_start=current_time - timedelta(days=2),
            presale_end=current_time + timedelta(hours=2),
            date_from=current_time - timedelta(days=2),
            date_to=timezone.datetime.combine(today, timezone.datetime.max.time())  # End of today
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    def test_queryset_returns_distinct_results(self):
        """Queryset should return distinct events (no duplicates from joins)"""
        event = self.create_event(
            talks_published=True,
            date_from=now() + timedelta(days=1),
            date_to=now() + timedelta(days=5),
        )

        # Create multiple submission types
        self.create_cfp(event, submission_deadline=now() + timedelta(days=5))
        SubmissionType.objects.create(
            event=event,
            name="Workshop",
            deadline=now() + timedelta(days=6)
        )

        qs = Event.objects.visible_on_startpage()
        self.assertEqual(qs.filter(id=event.id).count(), 1)  # Should appear only once