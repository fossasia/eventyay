import datetime
from datetime import timedelta
from io import BytesIO
from zoneinfo import ZoneInfo
from unittest.mock import patch

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
def test_event_timezone_serialization_and_fallback():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Timezone Org", slug="tz-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Timezone Event",
            slug="tz-event",
            date_from=now(),
            timezone="UTC",
        )
        event.settings.timezone = "Asia/Tokyo"

        # Prioritizes settings timezone
        assert get_event_timezone_name(event) == "Asia/Tokyo"
        assert get_event_timezone(event) == ZoneInfo("Asia/Tokyo")
        assert ReportGenerator(event).tz == ZoneInfo("Asia/Tokyo")

        user = User.objects.create(
            event=event,
            profile={"display_name": "Tz User"},
        )
        serializer_data = _config_serializer(event).data
        assert serializer_data["timezone"] == "Asia/Tokyo"
        assert get_event_config_for_user(event, user)["world"]["timezone"] == "Asia/Tokyo"

        # Falls back to event.timezone when settings.timezone is empty
        event.timezone = "Europe/Paris"
        event.settings.timezone = ""
        assert get_event_timezone_name(event) == "Europe/Paris"
        assert get_event_timezone(event) == ZoneInfo("Europe/Paris")
        assert ReportGenerator(event).tz == ZoneInfo("Europe/Paris")
        assert get_event_config_for_user(event, user)["world"]["timezone"] == "Europe/Paris"

        # Falls back to UTC when both settings.timezone and event.timezone are empty
        event.timezone = ""
        assert get_event_timezone_name(event) == "UTC"
        assert get_event_timezone(event) == ZoneInfo("UTC")
        assert ReportGenerator(event).tz == ZoneInfo("UTC")
        assert get_event_config_for_user(event, user)["world"]["timezone"] == "UTC"


@pytest.mark.django_db
def test_generate_room_views_multiday_and_abandoned_views():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Room Views Org", slug="rv-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Room Views Event",
            slug="rv-event",
            date_from=now(),
            timezone="UTC",
        )
        event.settings.timezone = "Europe/Berlin"
        tz = ZoneInfo("Europe/Berlin")

        room = Room.objects.create(
            event=event,
            name="Main Hall",
            module_config=[{"type": "livestream.native"}],
        )

        user1 = User.objects.create(
            event=event,
            profile={"display_name": "Active Viewer"},
        )
        user2 = User.objects.create(
            event=event,
            profile={"display_name": "Old Abandoned Viewer"},
        )

        # Range: 2026-11-18 14:00 to 2026-11-19 10:00 (begin.hour > end.hour, overnight multi-day)
        begin_dt = datetime.datetime(2026, 11, 18, 14, 0, tzinfo=tz)
        end_dt = datetime.datetime(2026, 11, 19, 10, 0, tzinfo=tz)

        # User 1 active during the evening
        _create_room_view(
            room=room,
            user=user1,
            start=begin_dt + timedelta(hours=1),
            end=begin_dt + timedelta(hours=2),
        )

        # User 2 abandoned view from 3 days ago (end is None)
        _create_room_view(
            room=room,
            user=user2,
            start=begin_dt - timedelta(days=3),
            end=None,
        )

        # Pass naive ISO strings as from frontend
        payload = {
            "begin": "2026-11-18T14:00",
            "end": "2026-11-19T10:00",
        }

        with patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            with scope(event=event):
                url = generate_room_views(event.pk, payload)
                assert url == "http://example.com/report.xlsx"

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["Main Hall"]
            rows = list(sheet.iter_rows(values_only=True))

            # Header row + data rows
            assert len(rows) > 1
            assert rows[0] == ("Date", "Time", "Viewership (approx. unique users)")

            # Check that User 1 is recorded and User 2 is not counted in 2026-11-18 buckets
            viewership_counts = [r[2] for r in rows[1:] if r[2] != ""]
            assert 1 in viewership_counts
            # User 2 should NOT inflate viewership to 2 users
            assert 2 not in viewership_counts


@pytest.mark.django_db
def test_generate_session_views_filters_abandoned_views():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Session Org", slug="session-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Session Event",
            slug="session-event",
            date_from=now(),
            timezone="UTC",
        )
        event.settings.timezone = "Europe/Berlin"
        tz = ZoneInfo("Europe/Berlin")

        room = Room.objects.create(
            event=event,
            name="Track 1",
            pretalx_id=101,
            module_config=[{"type": "livestream.native"}],
        )

        user1 = User.objects.create(
            event=event,
            profile={"display_name": "Session Viewer"},
        )
        user2 = User.objects.create(
            event=event,
            profile={"display_name": "Old Ghost Viewer"},
        )

        talk_start = datetime.datetime(2026, 11, 18, 10, 0, tzinfo=tz)
        talk_end = datetime.datetime(2026, 11, 18, 11, 0, tzinfo=tz)

        # User 1 viewed during talk
        _create_room_view(
            room=room,
            user=user1,
            start=talk_start + timedelta(minutes=10),
            end=talk_start + timedelta(minutes=40),
        )

        # User 2 abandoned view from days ago with end=None
        _create_room_view(
            room=room,
            user=user2,
            start=talk_start - timedelta(days=2),
            end=None,
        )

        mock_schedule = {
            "talks": [
                {
                    "title": "Keynote Presentation",
                    "room": 101,
                    "start": talk_start.isoformat(),
                    "end": talk_end.isoformat(),
                }
            ]
        }

        payload = {
            "begin": "2026-11-18T00:00",
            "end": "2026-11-18T23:59",
        }

        with patch("eventyay.features.analytics.graphs.tasks.get_schedule", return_value=mock_schedule), \
             patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            with scope(event=event):
                generate_session_views(event.pk, payload)

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["Sessions"]
            rows = list(sheet.iter_rows(values_only=True))

            # Row 0: Header, Row 1: Keynote Talk
            assert len(rows) == 2
            talk_row = rows[1]
            assert talk_row[0] == "Keynote Presentation"
            assert talk_row[1] == "Track 1"
            # Viewership should only count User 1 (1 viewer), excluding the ghost view
            assert talk_row[6] == 1


@pytest.mark.django_db
def test_generate_attendee_session_list_strictly_positive_duration():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Attendee Org", slug="att-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Attendee Event",
            slug="att-event",
            date_from=now(),
            timezone="UTC",
        )
        event.settings.timezone = "Europe/Berlin"
        tz = ZoneInfo("Europe/Berlin")

        room = Room.objects.create(
            event=event,
            name="Auditorium",
            pretalx_id=202,
            module_config=[{"type": "livestream.native"}],
        )

        user1 = User.objects.create(
            event=event,
            token_id="user-1",
            profile={"display_name": "Real Attendee"},
            traits=["attendee"],
        )
        user2 = User.objects.create(
            event=event,
            token_id="user-2",
            profile={"display_name": "Ghost Attendee"},
            traits=["attendee"],
        )

        talk_start = datetime.datetime(2026, 11, 18, 14, 0, tzinfo=tz)
        talk_end = datetime.datetime(2026, 11, 18, 15, 0, tzinfo=tz)

        # User 1 viewed for 30 minutes, plus an overlapping view from +20 to +50 minutes
        # Total merged watch time: +10 to +50 = 40 minutes (not 30+30=60)
        _create_room_view(
            room=room,
            user=user1,
            start=talk_start + timedelta(minutes=10),
            end=talk_start + timedelta(minutes=40),
        )
        _create_room_view(
            room=room,
            user=user1,
            start=talk_start + timedelta(minutes=20),
            end=talk_start + timedelta(minutes=50),
        )

        # User 2 abandoned view from 5 days ago (end=None)
        _create_room_view(
            room=room,
            user=user2,
            start=talk_start - timedelta(days=5),
            end=None,
        )

        mock_schedule = {
            "talks": [
                {
                    "title": "Deep Dive Session",
                    "room": 202,
                    "start": talk_start.isoformat(),
                    "end": talk_end.isoformat(),
                }
            ]
        }

        with patch("eventyay.features.analytics.graphs.tasks.get_schedule", return_value=mock_schedule), \
             patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            with scope(event=event):
                generate_attendee_session_list(event.pk, {})

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["Deep Dive Session"]
            rows = list(sheet.iter_rows(values_only=True))

            # Header structure: title row, talk metadata, column headers, data rows
            data_rows = rows[3:]
            # User 1 should be present with 40 merged minutes
            assert len(data_rows) == 1
            assert data_rows[0][1] == "user-1"
            assert data_rows[0][2] == "Real Attendee"
            assert data_rows[0][3] == 40
            # User 2 must NOT be included with 0 or negative minutes
            assert not any(r[1] == "user-2" for r in data_rows)


@pytest.mark.django_db
def test_generate_views_formats_with_event_timezone():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Views Org", slug="views-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Views Event",
            slug="views-event",
            date_from=now(),
            timezone="UTC",
        )
        event.settings.timezone = "Asia/Kolkata"
        tz = ZoneInfo("Asia/Kolkata")

        room = Room.objects.create(
            event=event,
            name="Hall A",
            module_config=[{"type": "livestream.native"}],
        )

        user = User.objects.create(
            event=event,
            token_id="user-ist",
            profile={"display_name": "Kolkata Viewer"},
        )

        # 10:00 IST = 04:30 UTC
        view_start = datetime.datetime(2026, 11, 18, 10, 0, tzinfo=tz)
        view_end = datetime.datetime(2026, 11, 18, 11, 30, tzinfo=tz)

        _create_room_view(
            room=room,
            user=user,
            start=view_start,
            end=view_end,
        )
        _create_event_view(
            event=event,
            user=user,
            start=view_start,
            end=view_end,
        )

        payload = {
            "begin": "2026-11-18T00:00:00+05:30",
            "end": "2026-11-18T23:59:59+05:30",
        }

        with patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            with scope(event=event):
                generate_views(event.pk, payload)

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["Room views"]
            rows = list(sheet.iter_rows(values_only=True))

            assert len(rows) == 2
            # Verify formatted date in IST timezone (10:00:00, not 04:30:00 UTC)
            assert rows[1][1] == "18.11.2026 10:00:00"
            assert rows[1][2] == "18.11.2026 11:30:00"
            assert rows[1][5] == "Kolkata Viewer"


@pytest.mark.django_db
def test_event_timezone_invalid_fallback():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Bad TZ Org", slug="bad-tz-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Bad TZ Event",
            slug="bad-tz-event",
            date_from=now(),
            timezone="UTC",
        )
        event.settings.timezone = "NonExistent/Invalid_Timezone"
        # Falls back safely to UTC without throwing ZoneInfoNotFoundError
        assert get_event_timezone(event) == ZoneInfo("UTC")
        assert ReportGenerator(event).tz == ZoneInfo("UTC")


@pytest.mark.django_db
def test_generate_room_views_with_empty_input():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Empty Input Org", slug="ei-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Empty Input Event",
            slug="ei-event",
            date_from=now(),
            date_to=now() + timedelta(days=1),
            timezone="UTC",
        )
        room = Room.objects.create(
            event=event,
            name="Lobby",
            module_config=[{"type": "livestream.native"}],
        )

        with patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            with scope(event=event):
                # Calling with None and with {} should both succeed using event.date_from/date_to fallback
                url = generate_room_views(event.pk, None)
                assert url == "http://example.com/report.xlsx"
                assert saved_content is not None


@pytest.mark.django_db
def test_report_generator_pdf_build():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="PDF Org", slug="pdf-org")
        event = Event.objects.create(
            organizer=organizer,
            name="PDF Event",
            slug="pdf-event",
            date_from=now(),
            date_to=now() + timedelta(days=2),
            timezone="UTC",
        )
        room = Room.objects.create(
            event=event,
            name="Keynote Stage",
            pretalx_id=999,
            module_config=[{"type": "livestream.native"}],
        )
        user = User.objects.create(
            event=event,
            token_id="user-pdf",
            profile={"display_name": "PDF Viewer"},
            type=User.UserType.PERSON,
        )
        _create_room_view(
            room=room,
            user=user,
            start=event.date_from + timedelta(hours=1),
            end=None,  # Abandoned view to verify Coalesce duration logic
        )

        with patch("eventyay.features.analytics.graphs.report.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/summary.pdf"

            with scope(event=event):
                # Build without graph rendering to test PDF story & table generation
                generator = ReportGenerator(event, pdf_graphs=False)
                cf = generator.build(input=None)
                assert cf.file.url == "http://example.com/summary.pdf"
                assert saved_content is not None
                # PDF magic header
                assert saved_content.startswith(b"%PDF")
                # Assert configured event dates take precedence
                assert generator.date_begin == event.date_from
                assert generator.date_end == event.date_to

                # When event dates are absent, verify fallback to RoomView extrema
                event_no_dates = Event.objects.create(
                    organizer=organizer,
                    name="No Dates Event",
                    slug="no-dates-event",
                    date_from=now(),
                    date_to=now() + timedelta(days=1),
                    timezone="UTC",
                )
                room_no_dates = Room.objects.create(
                    event=event_no_dates,
                    name="Room 1",
                    module_config=[{"type": "livestream.native"}],
                )
                user_no_dates = User.objects.create(
                    event=event_no_dates,
                    profile={"display_name": "Viewer 1"},
                    type=User.UserType.PERSON,
                )
                t1 = now() - timedelta(days=2)
                t2 = now() - timedelta(days=1)
                _create_room_view(room=room_no_dates, user=user_no_dates, start=t1, end=t2)

                event_no_dates.date_from = None
                event_no_dates.date_to = None
                gen_no_dates = ReportGenerator(event_no_dates, pdf_graphs=False)
                assert gen_no_dates.date_begin == t1
                assert gen_no_dates.date_end == t2


@pytest.mark.django_db
def test_pdf_report_duration_clipped_to_bounds():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Clip Org", slug="clip-org")
        base_time = now()
        report_start = base_time
        report_end = base_time + timedelta(hours=1)  # 60 minute report window

        event = Event.objects.create(
            organizer=organizer,
            name="Clip Event",
            slug="clip-event",
            date_from=report_start,
            date_to=report_end,
            timezone="UTC",
        )
        room = Room.objects.create(
            event=event,
            name="Stream Stage",
            module_config=[{"type": "livestream.native"}],
        )

        # User 1: starts 5 minutes before report end (report_end - 5m) and stays 30 minutes after (report_end + 30m)
        # Total duration = 35m, but duration within report interval must be clipped to 5m.
        user1 = User.objects.create(
            event=event,
            profile={"display_name": "Crossing End Viewer"},
            type=User.UserType.PERSON,
        )
        _create_room_view(
            room=room,
            user=user1,
            start=report_end - timedelta(minutes=5),
            end=report_end + timedelta(minutes=30),
        )

        # User 2: starts 30 minutes before report start (report_start - 30m) and ends 15 minutes after (report_start + 15m)
        # Total duration = 45m, but duration within report interval must be clipped to 15m.
        user2 = User.objects.create(
            event=event,
            profile={"display_name": "Crossing Start Viewer"},
            type=User.UserType.PERSON,
        )
        _create_room_view(
            room=room,
            user=user2,
            start=report_start - timedelta(minutes=30),
            end=report_start + timedelta(minutes=15),
        )

        with scope(event=event):
            generator = ReportGenerator(event, pdf_graphs=False)
            story = generator.story_for_room(room)
            # Find the stats table in the room story
            tables = [el for el in story if isinstance(el, Table)]
            assert len(tables) > 0
            stats_table = tables[0]

            # Row 0: Total number of unique viewers -> "2"
            assert stats_table._cellvalues[0][1] == "2"
            # Row 1: Average time spent in room -> (5m + 15m) / 2 = 10m -> "0:10:00"
            assert stats_table._cellvalues[1][1] == "0:10:00"
            # Row 2: Median time spent in room -> (5m + 15m) / 2 = 10m -> "0:10:00"
            assert stats_table._cellvalues[2][1] == "0:10:00"


@pytest.mark.django_db
def test_event_task_call_invocation_paths():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="Task Org", slug="task-org")
        event = Event.objects.create(
            organizer=organizer,
            name="Task Event",
            slug="task-event",
            date_from=now(),
            timezone="UTC",
        )

        @app.task(base=EventTask)
        def dummy_task(event, **kwargs):
            return event

        # 1. Positional argument: integer PK
        res1 = dummy_task(event.pk)
        assert isinstance(res1, Event)
        assert res1.pk == event.pk

        # 2. Positional argument: Event instance
        res2 = dummy_task(event)
        assert isinstance(res2, Event)
        assert res2.pk == event.pk

        # 3. Keyword argument 'event_id': integer PK
        res3 = dummy_task(event_id=event.pk)
        assert isinstance(res3, Event)
        assert res3.pk == event.pk

        # 4. Keyword argument 'event_id': Event instance
        res4 = dummy_task(event_id=event)
        assert isinstance(res4, Event)
        assert res4.pk == event.pk

        # 5. Keyword argument 'event': integer PK
        res5 = dummy_task(event=event.pk)
        assert isinstance(res5, Event)
        assert res5.pk == event.pk

        # 6. Keyword argument 'event': Event instance
        res6 = dummy_task(event=event)
        assert isinstance(res6, Event)
        assert res6.pk == event.pk


@pytest.mark.django_db
def test_attendee_session_list_dst_transition():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="DST Org", slug="dst-org")
        event = Event.objects.create(
            organizer=organizer,
            name="DST Event",
            slug="dst-event",
            date_from=now(),
            timezone="Europe/Berlin",
        )
        event.settings.timezone = "Europe/Berlin"

        room = Room.objects.create(
            event=event,
            name="DST Hall",
            pretalx_id=101,
            module_config=[{"type": "livestream.native"}],
        )

        user = User.objects.create(
            event=event,
            token_id="user-dst",
            profile={"display_name": "DST Viewer"},
            traits=["attendee"],
            type=User.UserType.PERSON,
        )

        # In Europe/Berlin, on Sunday Oct 25 2026, clocks turn back 1 hour (from CEST +02:00 to CET +01:00 at 03:00)
        # Session from 02:15 CEST (00:15 UTC) to 02:45 CET (01:45 UTC): physical duration is 90 minutes.
        start_utc = datetime.datetime(2026, 10, 25, 0, 15, tzinfo=datetime.timezone.utc)
        end_utc = datetime.datetime(2026, 10, 25, 1, 45, tzinfo=datetime.timezone.utc)

        fake_schedule = {
            "talks": [
                {
                    "title": "Overnight DST Talk",
                    "room": 101,
                    # Provide ISO strings with explicit offsets
                    "start": "2026-10-25T02:15:00+02:00",
                    "end": "2026-10-25T02:45:00+01:00",
                }
            ]
        }

        # User watched the full 90-minute session
        _create_room_view(
            room=room,
            user=user,
            start=start_utc,
            end=end_utc,
        )

        with patch("eventyay.features.analytics.graphs.tasks.get_schedule", return_value=fake_schedule), \
             patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:

            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            with scope(event=event):
                generate_attendee_session_list(event.pk, {})

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["Overnight DST Talk"]
            rows = list(sheet.iter_rows(values_only=True))

            # Rows: [0] title, [1] session info, [2] header, [3] attendee data
            assert len(rows) == 4
            data_row = rows[3]
            # Duration in minutes must be exactly 90
            assert data_row[3] == 90


@pytest.mark.django_db
def test_parse_task_date_range_dst_fallback_and_raw_views_export():
    organizer = Organizer.objects.create(name="DST Fallback Org", slug="dst-fb-org")
    event = Event.objects.create(
        organizer=organizer,
        name="DST Fallback Event",
        slug="dst-fb-event",
        date_from=now(),
        timezone="Europe/Berlin",
    )
    event.settings.timezone = "Europe/Berlin"
    tz = ZoneInfo("Europe/Berlin")

    # In Berlin autumn transition on 2026-10-25:
    # 02:45:00+02:00 corresponds to 00:45:00 UTC
    # 02:15:00+01:00 corresponds to 01:15:00 UTC
    # 00:45:00 UTC is 30 minutes earlier than 01:15:00 UTC.
    raw_input = {
        "begin": "2026-10-25T02:45:00+02:00",
        "end": "2026-10-25T02:15:00+01:00",
    }
    with scope(event=event):
        begin, end = _parse_task_date_range(event, raw_input, tz)

    # Must preserve chronological order and NOT swap them
    begin_utc = begin.astimezone(datetime.timezone.utc)
    end_utc = end.astimezone(datetime.timezone.utc)
    assert begin_utc == datetime.datetime(2026, 10, 25, 0, 45, tzinfo=datetime.timezone.utc)
    assert end_utc == datetime.datetime(2026, 10, 25, 1, 15, tzinfo=datetime.timezone.utc)
    assert begin_utc < end_utc

    # Create room and user
    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name="Fallback Hall",
            module_config=[{"type": "livestream.native"}],
        )
        user = User.objects.create(
            event=event,
            token_id="user-fb",
            profile={"display_name": "Fallback Viewer"},
            traits=["attendee"],
            type=User.UserType.PERSON,
        )

        # View from 00:50 UTC to 01:10 UTC (falls inside the 00:45 UTC to 01:15 UTC window)
        view_start = datetime.datetime(2026, 10, 25, 0, 50, tzinfo=datetime.timezone.utc)
        view_end = datetime.datetime(2026, 10, 25, 1, 10, tzinfo=datetime.timezone.utc)
        _create_room_view(room=room, user=user, start=view_start, end=view_end)
        _create_event_view(event=event, user=user, start=view_start, end=view_end)

        with patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            # Call generate_views task directly (scoped internally with scope(event=event))
            generate_views(event.pk, raw_input)

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))

            room_sheet = wb["Room views"]
            room_rows = list(room_sheet.iter_rows(values_only=True))
            # Header is row 0, data is row 1
            assert len(room_rows) == 2
            assert room_rows[1][0] == "Fallback Hall"
            assert room_rows[1][5] == "Fallback Viewer"

            event_sheet = wb["Event views"]
            event_rows = list(event_sheet.iter_rows(values_only=True))
            assert len(event_rows) == 2
            assert event_rows[1][4] == "Fallback Viewer"


@pytest.mark.django_db
def test_session_views_open_view_dst_spring_forward():
    organizer = Organizer.objects.create(name="DST Spring Org", slug="dst-sp-org")
    event = Event.objects.create(
        organizer=organizer,
        name="DST Spring Event",
        slug="dst-sp-event",
        date_from=now(),
        timezone="Europe/Berlin",
    )
    event.settings.timezone = "Europe/Berlin"

    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name="Spring Hall",
            pretalx_id=202,
            module_config=[{"type": "livestream.native"}],
        )
        user = User.objects.create(
            event=event,
            token_id="user-spring",
            profile={"display_name": "Spring Viewer"},
            traits=["attendee"],
            type=User.UserType.PERSON,
        )

        # In Berlin on Sunday March 29, 2026: clocks jump from 02:00 CET (+01:00) to 03:00 CEST (+02:00)
        # Talk starts at 04:30 CEST (02:30 UTC) and ends at 05:30 CEST (03:30 UTC).
        # Viewer joined at 01:00 CET (00:00 UTC) - open view (end=None).
        # Elapsed physical time between join and talk start is 2 hours 30 minutes (<= 3 hours).
        # Under the old local-time subtraction (04:30 CEST - 3h = 01:30 CET = 00:30 UTC), this view at 00:00 UTC was erroneously excluded.
        # With UTC lookback (02:30 UTC - 3h = 23:30 UTC), this view is correctly included.
        talk_start_utc = datetime.datetime(2026, 3, 29, 2, 30, tzinfo=datetime.timezone.utc)
        view_start_utc = datetime.datetime(2026, 3, 29, 0, 0, tzinfo=datetime.timezone.utc)
        _create_room_view(room=room, user=user, start=view_start_utc, end=None)

        fake_schedule = {
            "talks": [
                {
                    "title": "Spring Talk",
                    "room": 202,
                    "start": "2026-03-29T04:30:00+02:00",
                    "end": "2026-03-29T05:30:00+02:00",
                }
            ]
        }

        with patch("eventyay.features.analytics.graphs.tasks.get_schedule", return_value=fake_schedule), \
             patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            # Call generate_session_views without external scope (tests internal scoping too)
            generate_session_views(
                event.pk,
                {
                    "begin": "2026-03-29T00:00:00+02:00",
                    "end": "2026-03-29T23:59:59+02:00",
                },
            )

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["Sessions"]
            rows = list(sheet.iter_rows(values_only=True))
            assert len(rows) == 2
            # Title, Room, Start date, Start time, End date, End time, Viewership
            assert rows[1][0] == "Spring Talk"
            assert rows[1][6] == 1  # 1 viewer counted!


@pytest.mark.django_db
def test_parse_task_date_range_non_dict_payload():
    with scopes_disabled():
        organizer = Organizer.objects.create(name="NonDict Org", slug="nondict-org")
        event = Event.objects.create(
            organizer=organizer,
            name="NonDict Event",
            slug="nondict-event",
            date_from=now(),
            timezone="UTC",
        )
        tz = ZoneInfo("UTC")

        # Passing non-dict truthy values (e.g. list, string, int) must not raise AttributeError
        for invalid_input in [["invalid"], "string", 123, ("tuple",)]:
            begin, end = _parse_task_date_range(event, invalid_input, tz)
            assert isinstance(begin, datetime.datetime)
            assert isinstance(end, datetime.datetime)
            assert begin < end


@pytest.mark.django_db
def test_room_views_dst_fallback_repeated_hour_buckets():
    organizer = Organizer.objects.create(name="DST Buckets Org", slug="dst-b-org")
    event = Event.objects.create(
        organizer=organizer,
        name="DST Buckets Event",
        slug="dst-b-event",
        date_from=now(),
        timezone="Europe/Berlin",
    )
    event.settings.timezone = "Europe/Berlin"
    tz = ZoneInfo("Europe/Berlin")

    with scope(event=event):
        room = Room.objects.create(
            event=event,
            name="DST Bucket Hall",
            module_config=[{"type": "livestream.native"}],
        )
        user = User.objects.create(
            event=event,
            token_id="user-dst-b",
            profile={"display_name": "DST Bucket Viewer"},
            traits=["attendee"],
            type=User.UserType.PERSON,
        )

        # In Berlin on Sunday Oct 25, 2026: 25-hour day (02:00 occurs twice: +02:00 and +01:00)
        # Create a view during the second 02:xx hour (01:15 UTC to 01:45 UTC, wall time 02:15 CET)
        view_start = datetime.datetime(2026, 10, 25, 1, 15, tzinfo=datetime.timezone.utc)
        view_end = datetime.datetime(2026, 10, 25, 1, 45, tzinfo=datetime.timezone.utc)
        _create_room_view(room=room, user=user, start=view_start, end=view_end)

        with patch("eventyay.features.analytics.graphs.tasks.StoredFile") as mock_stored_file:
            saved_content = None

            def fake_save(filename, content):
                nonlocal saved_content
                saved_content = content.read()

            mock_file = mock_stored_file.objects.create.return_value
            mock_file.file.save.side_effect = fake_save
            mock_file.file.url = "http://example.com/report.xlsx"

            generate_room_views(
                event.pk,
                {
                    "begin": "2026-10-25T00:00:00+02:00",
                    "end": "2026-10-25T23:59:59+01:00",
                },
            )

            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["DST Bucket Hall"]
            rows = list(sheet.iter_rows(values_only=True))

            # Header is row 0; for a 25-hour day from 00:00 to 23:59:59 with 5-minute buckets:
            # 25 hours * 12 buckets/hour = 300 buckets (+ 1 endpoint bucket = 301 bucket rows)
            # Row 0: header -> total 302 rows
            assert len(rows) >= 300

            # Find the row corresponding to 02:15 during the second hour (viewers should be 1)
            active_rows = [r for r in rows[1:] if r[2] == 1]
            assert len(active_rows) > 0

            # Also test a custom date range spanning within the repeated hour (02:30+02:00 to 02:15+01:00)
            # which spans 45 physical minutes in UTC (00:30 UTC to 01:15 UTC).
            # Verifies that UTC boundary comparison prevents skipping the repeated hour.
            generate_room_views(
                event.pk,
                {
                    "begin": "2026-10-25T02:30:00+02:00",
                    "end": "2026-10-25T02:15:00+01:00",
                },
            )
            assert saved_content is not None
            wb = load_workbook(filename=BytesIO(saved_content))
            sheet = wb["DST Bucket Hall"]
            repeated_hour_rows = list(sheet.iter_rows(values_only=True))
            # 45 minutes = 9 intervals of 5 minutes (+ 1 header row = 10 rows)
            assert len(repeated_hour_rows) >= 10



