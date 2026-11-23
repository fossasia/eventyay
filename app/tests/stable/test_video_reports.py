import datetime
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled
from openpyxl import load_workbook
from reportlab.platypus import Table

from eventyay.base.models import Event, Organizer, Room, RoomView, User
from eventyay.base.models.event import EventView
from eventyay.base.services.event import (
    _config_serializer,
    get_event_config_for_user,
    get_event_timezone_name,
)
from eventyay.celery_app import app
from eventyay.core.tasks import EventTask
from eventyay.features.analytics.graphs.report import ReportGenerator
from eventyay.features.analytics.graphs.tasks import (
    _parse_task_date_range,
    generate_attendee_session_list,
    generate_room_views,
    generate_session_views,
    generate_views,
    get_event_timezone,
)


def _create_room_view(room, user, start, end):
    rv = RoomView.objects.create(room=room, user=user, end=end)
    RoomView.objects.filter(pk=rv.pk).update(start=start)
    return rv


def _create_event_view(event, user, start, end):
    ev = EventView.objects.create(event=event, user=user, end=end)
    EventView.objects.filter(pk=ev.pk).update(start=start)
    return ev


@pytest.mark.django_db
def test_event_timezone_and_fallbacks():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Tz Org", slug="tz-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Tz Event",
            slug="tz-event",
            date_from=now(),
            timezone="UTC",
        )
        user = User.objects.create(event=event, profile={"display_name": "Tz User"})

        # 1. Prioritizes settings.timezone
        event.settings.timezone = "Asia/Tokyo"
        assert get_event_timezone_name(event) == "Asia/Tokyo"
        assert get_event_timezone(event) == ZoneInfo("Asia/Tokyo")
        assert ReportGenerator(event).tz == ZoneInfo("Asia/Tokyo")
        assert _config_serializer(event).data["timezone"] == "Asia/Tokyo"
        assert get_event_config_for_user(event, user)["world"]["timezone"] == "Asia/Tokyo"

        # 2. Falls back to event.timezone when settings.timezone is empty
        event.timezone = "Europe/Paris"
        event.settings.timezone = ""
        assert get_event_timezone_name(event) == "Europe/Paris"
        assert get_event_timezone(event) == ZoneInfo("Europe/Paris")
        assert ReportGenerator(event).tz == ZoneInfo("Europe/Paris")
        assert get_event_config_for_user(event, user)["world"]["timezone"] == "Europe/Paris"

        # 3. Falls back to UTC when both are empty
        event.timezone = ""
        assert get_event_timezone_name(event) == "UTC"
        assert get_event_timezone(event) == ZoneInfo("UTC")
        assert ReportGenerator(event).tz == ZoneInfo("UTC")
        assert get_event_config_for_user(event, user)["world"]["timezone"] == "UTC"

        # 4. Falls back to UTC for invalid timezone string
        event.settings.timezone = "Mars/Phobos"
        assert get_event_timezone(event) == ZoneInfo("UTC")


@pytest.mark.django_db
def test_task_date_range_parsing():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Range Org", slug="range-org")
        tz = ZoneInfo("Europe/Berlin")
        start = datetime.datetime(2026, 6, 1, 10, 0, tzinfo=tz)
        end = datetime.datetime(2026, 6, 3, 18, 0, tzinfo=tz)
        event = Event.objects.create(
            organizer=organizer,
            name="Range Event",
            slug="range-event",
            date_from=start,
            date_to=end,
        )

        # 1. Normal payload
        b, e = _parse_task_date_range(event, {"begin": "2026-06-01T10:00", "end": "2026-06-02T12:00"}, tz)
        assert b == datetime.datetime(2026, 6, 1, 10, 0, tzinfo=tz)
        assert e == datetime.datetime(2026, 6, 2, 12, 0, tzinfo=tz)

        # 2. Empty or non-dict inputs fall back to event.date_from and event.date_to
        for non_dict in ({}, None, "invalid", [1, 2, 3]):
            fb_b, fb_e = _parse_task_date_range(event, non_dict, tz)
            assert fb_b == start
            assert fb_e == end

        # 3. Inverted range is automatically swapped in UTC
        rev_b, rev_e = _parse_task_date_range(event, {"begin": "2026-06-02T12:00", "end": "2026-06-01T10:00"}, tz)
        assert rev_b == datetime.datetime(2026, 6, 1, 10, 0, tzinfo=tz)
        assert rev_e == datetime.datetime(2026, 6, 2, 12, 0, tzinfo=tz)


@pytest.mark.django_db
def test_event_task_call_invocation():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Task Org", slug="task-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Task Event",
            slug="task-event",
            date_from=now(),
            timezone="UTC",
        )

    received = {}

    @app.task(base=EventTask)
    def dummy_task(event, **kwargs):
        received["event"] = event
        received["kwargs"] = kwargs
        # Verify execution occurs within event scope
        Room.objects.filter(event=event).count()
        return "ok"

    # 1. event_id kwarg (int and Event instance)
    dummy_task(event_id=event.pk)
    assert received["event"] == event
    dummy_task(event_id=event)
    assert received["event"] == event

    # 2. event kwarg (int and Event instance)
    dummy_task(event=event.pk)
    assert received["event"] == event
    dummy_task(event=event)
    assert received["event"] == event

    # 3. First positional argument (int and Event instance)
    dummy_task(event.pk)
    assert received["event"] == event
    dummy_task(event)
    assert received["event"] == event


@pytest.mark.django_db
def test_room_views_multiday_abandoned_and_dst():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="RV Org", slug="rv-org")
        event = Event.objects.create(
            organizer=organizer,
            name="RV Event",
            slug="rv-event",
            date_from=now(),
            timezone="Europe/Berlin",
        )
        event.settings.timezone = "Europe/Berlin"
        tz = ZoneInfo("Europe/Berlin")

        room = Room.objects.create(event=event, name="Main Hall", module_config=[{"type": "livestream.native"}])
        user1 = User.objects.create(event=event, profile={"display_name": "Active User"})
        user2 = User.objects.create(event=event, profile={"display_name": "Abandoned User"})

        # Multi-day span: Nov 18 14:00 to Nov 19 10:00 (begin.hour > end.hour)
        begin_dt = datetime.datetime(2026, 11, 18, 14, 0, tzinfo=tz)
        _create_room_view(room=room, user=user1, start=begin_dt + timedelta(hours=1), end=begin_dt + timedelta(hours=2))
        _create_room_view(room=room, user=user2, start=begin_dt - timedelta(days=3), end=None)

        with patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_sf:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_sf.objects.create.return_value.file.save.side_effect = fake_save

            # 1. Verify multi-day and abandoned view capping
            generate_room_views(event.pk, {"begin": "2026-11-18T14:00", "end": "2026-11-19T10:00"})
            wb = load_workbook(filename=BytesIO(saved_content))
            rows = list(wb["Main Hall"].iter_rows(values_only=True))
            viewership = [r[2] for r in rows[1:] if r[2] != ""]
            assert 1 in viewership
            assert 2 not in viewership  # User 2 abandoned view > 3h is capped and excluded

            # 2. Repeated DST hour (Berlin fallback 25-hour day) custom range spanning 02:30+02:00 to 02:15+01:00
            generate_room_views(event.pk, {"begin": "2026-10-25T02:30:00+02:00", "end": "2026-10-25T02:15:00+01:00"})
            wb = load_workbook(filename=BytesIO(saved_content))
            assert len(list(wb["Main Hall"].iter_rows(values_only=True))) >= 10


@pytest.mark.django_db
def test_session_views_abandoned_and_dst_lookback():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="SV Org", slug="sv-org")
        event = Event.objects.create(
            organizer=organizer,
            name="SV Event",
            slug="sv-event",
            date_from=now(),
            timezone="Europe/Berlin",
        )
        event.settings.timezone = "Europe/Berlin"
        tz = ZoneInfo("Europe/Berlin")

        room = Room.objects.create(event=event, name="Track 1", pretalx_id=101, module_config=[{"type": "livestream.native"}])
        user1 = User.objects.create(event=event, profile={"display_name": "Active Viewer"})
        user2 = User.objects.create(event=event, profile={"display_name": "Ghost Viewer"})

        talk_start = datetime.datetime(2026, 11, 20, 10, 0, tzinfo=tz)
        talk_end = datetime.datetime(2026, 11, 20, 11, 0, tzinfo=tz)
        _create_room_view(room=room, user=user1, start=talk_start + timedelta(minutes=10), end=talk_end)
        _create_room_view(room=room, user=user2, start=talk_start - timedelta(days=2), end=None)

        schedule = {"talks": [{"title": "Talk 1", "room": 101, "start": talk_start.isoformat(), "end": talk_end.isoformat()}]}

        with patch("eventyay.features.analytics.graphs.tasks.get_schedule", return_value=schedule), \
             patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_sf:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_sf.objects.create.return_value.file.save.side_effect = fake_save

            # 1. Filters out stale abandoned view from 2 days prior
            generate_session_views(event.pk, {"begin": "2026-11-20T08:00", "end": "2026-11-20T18:00"})
            wb = load_workbook(filename=BytesIO(saved_content))
            assert list(wb["Sessions"].iter_rows(values_only=True))[1][6] == 1

            # 2. DST spring forward (March 29, 2026): open view at 00:00 UTC (01:00 CET)
            # Talk at 04:30 CEST (02:30 UTC); 2.5h physical elapsed time is <= 3h lookback in UTC
            _create_room_view(room=room, user=user1, start=datetime.datetime(2026, 3, 29, 0, 0, tzinfo=datetime.timezone.utc), end=None)
            schedule_dst = {"talks": [{"title": "DST Talk", "room": 101, "start": "2026-03-29T04:30:00+02:00", "end": "2026-03-29T05:30:00+02:00"}]}
            with patch("eventyay.features.analytics.graphs.tasks.get_schedule", return_value=schedule_dst):
                generate_session_views(event.pk, {"begin": "2026-03-29T00:00:00+02:00", "end": "2026-03-29T23:59:59+02:00"})
                wb = load_workbook(filename=BytesIO(saved_content))
                assert list(wb["Sessions"].iter_rows(values_only=True))[1][6] >= 1


@pytest.mark.django_db
def test_attendee_session_list_overlapping_intervals():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Att Org", slug="att-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Att Event",
            slug="att-event",
            date_from=now(),
            timezone="Europe/Berlin",
        )
        event.settings.timezone = "Europe/Berlin"
        tz = ZoneInfo("Europe/Berlin")

        room = Room.objects.create(event=event, name="Auditorium", pretalx_id=303, module_config=[{"type": "livestream.native"}])
        user = User.objects.create(event=event, token_id="token-multi", profile={"display_name": "Multi Device"}, traits=["attendee"])

        talk_start = datetime.datetime(2026, 11, 20, 10, 0, tzinfo=tz)
        talk_end = datetime.datetime(2026, 11, 20, 10, 30, tzinfo=tz)  # 30-minute talk

        # Overlapping sessions on 2 devices:
        # Tab 1: 10:00 to 10:20 (20 min)
        # Tab 2: 10:10 to 10:30 (20 min)
        # Raw sum is 40 min, but merged interval spans 10:00 to 10:30 = exactly 30 min.
        _create_room_view(room=room, user=user, start=talk_start, end=talk_start + timedelta(minutes=20))
        _create_room_view(room=room, user=user, start=talk_start + timedelta(minutes=10), end=talk_end)

        schedule = {"talks": [{"title": "Interval Talk", "room": 303, "start": talk_start.isoformat(), "end": talk_end.isoformat()}]}

        with patch("eventyay.features.analytics.graphs.tasks.get_schedule", return_value=schedule), \
             patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_sf:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_sf.objects.create.return_value.file.save.side_effect = fake_save

            generate_attendee_session_list(event.pk, {})
            wb = load_workbook(filename=BytesIO(saved_content))
            rows = list(wb["Interval Talk"].iter_rows(values_only=True))
            # Row 3 is data row; column index 3 is duration (minutes)
            assert rows[3][3] == 30


@pytest.mark.django_db
def test_raw_views_export_timezone_and_formatting():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Views Org", slug="views-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Views Event",
            slug="views-event",
            date_from=now(),
            timezone="Asia/Tokyo",
        )
        event.settings.timezone = "Asia/Tokyo"
        tz = ZoneInfo("Asia/Tokyo")

        room = Room.objects.create(event=event, name="Tokyo Hall")
        user = User.objects.create(event=event, profile={"display_name": "Tokyo Viewer"})

        start_utc = datetime.datetime(2026, 11, 15, 0, 0, tzinfo=datetime.timezone.utc)
        end_utc = datetime.datetime(2026, 11, 15, 1, 0, tzinfo=datetime.timezone.utc)
        _create_room_view(room=room, user=user, start=start_utc, end=end_utc)
        _create_event_view(event=event, user=user, start=start_utc, end=end_utc)

        with patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_sf:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_sf.objects.create.return_value.file.save.side_effect = fake_save

            generate_views(event.pk, {"begin": "2026-11-15T09:00:00+09:00", "end": "2026-11-15T10:00:00+09:00"})
            wb = load_workbook(filename=BytesIO(saved_content))

            # 00:00 UTC is 09:00 in Asia/Tokyo (+09:00)
            room_row = list(wb["Room views"].iter_rows(values_only=True))[1]
            assert "15.11.2026 09:00:00" in room_row[1]
            assert room_row[0] == "Tokyo Hall"

            event_row = list(wb["Event views"].iter_rows(values_only=True))[1]
            assert "15.11.2026 09:00:00" in event_row[0]


@pytest.mark.django_db
def test_pdf_report_generation_and_clipping():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="PDF Org", slug="pdf-org")
        event = Event.objects.create(
            organizer=organizer,
            name="PDF Event",
            slug="pdf-event",
            date_from=now(),
            timezone="Europe/Berlin",
        )
        event.settings.timezone = "Europe/Berlin"
        tz = ZoneInfo("Europe/Berlin")

        room = Room.objects.create(event=event, name="PDF Hall", pretalx_id=404, module_config=[{"type": "livestream.native"}])
        user = User.objects.create(event=event, profile={"display_name": "PDF Viewer"}, type=User.UserType.PERSON)

        # Report window: 10:00 to 11:00 (1 hour = 60 min)
        # View extends from 09:00 to 12:00 (3 hours = 180 min)
        # SQL clipping must clip duration to exactly 60 minutes
        window_start = datetime.datetime(2026, 11, 20, 10, 0, tzinfo=tz)
        window_end = datetime.datetime(2026, 11, 20, 11, 0, tzinfo=tz)
        _create_room_view(room=room, user=user, start=window_start - timedelta(hours=1), end=window_end + timedelta(hours=1))

        schedule = {"talks": [{"title": "PDF Talk", "room": 404, "start": window_start.isoformat(), "end": window_end.isoformat()}]}

        with patch("eventyay.features.analytics.graphs.report.get_schedule", return_value=schedule):
            rg = ReportGenerator(event, pdf_graphs=False, input={"begin": window_start.isoformat(), "end": window_end.isoformat()})
            story = rg.get_story()
            tables = [el for el in story if isinstance(el, Table)]
            assert len(tables) > 0

            # Find cell containing total duration (should be clipped to 1h, not 3h)
            table_texts = [str(cell) for t in tables for row in t._cellvalues for cell in row]
            assert "1:00:00" in table_texts
            assert "3:00:00" not in table_texts
