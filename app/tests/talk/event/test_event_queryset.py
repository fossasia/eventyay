from django.test import TestCase
from django.utils.timezone import now, timedelta

from eventyay.base.models.event import Event
from eventyay.base.models.organizer import Organizer
from eventyay.base.models.cfp import CfP
from eventyay.base.models.type import SubmissionType


class EventQuerySetTest(TestCase):

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
        """
        Updates the existing CfP (OneToOne with Event)
        """

        # Get existing CfP (created automatically)
        cfp = event.cfp

        # Update deadline
        cfp.deadline = deadline
        cfp.save()

        # Create submission type
        submission_type = SubmissionType.objects.create(
            event=event,
            name="Talk",
            deadline=submission_deadline
        )

        cfp.default_type = submission_type
        cfp.save()

        return cfp


    # ===============================
    # ✅ Tickets Logic
    # ===============================

    def test_future_event_with_live_tickets_is_visible(self):
        event = self.create_event(
            tickets_published=True,
            presale_start=now() - timedelta(days=1),
            presale_end=now() + timedelta(days=2),
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    # ===============================
    # ❌ Past Event Excluded
    # ===============================

    def test_past_event_is_not_visible(self):
        event = self.create_event(
            date_to=now() - timedelta(days=1),
            tickets_published=True,
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    # ===============================
    # ❌ Not Live Excluded
    # ===============================

    def test_not_live_event_is_not_visible(self):
        event = self.create_event(
            live=False,
            tickets_published=True,
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)

    # ===============================
    # ✅ Valid CFP Deadline
    # ===============================

    def test_event_with_valid_cfp_is_visible(self):
        event = self.create_event(
            talks_published=True
        )

        self.create_cfp(
            event,
            deadline=now() + timedelta(days=5),
            submission_deadline=now() + timedelta(days=5)
        )

        qs = Event.objects.visible_on_startpage()
        self.assertIn(event, qs)

    # ===============================
    # ❌ Expired CFP + Expired SubmissionType
    # ===============================

    def test_event_with_expired_cfp_is_not_visible(self):
        event = self.create_event(
            talks_published=True
        )

        self.create_cfp(
            event,
            deadline=now() - timedelta(days=1),
            submission_deadline=now() - timedelta(days=1)
        )

        qs = Event.objects.visible_on_startpage()
        self.assertNotIn(event, qs)
