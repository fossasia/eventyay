import re
from collections import defaultdict
from datetime import timedelta
from io import BytesIO

import dateutil
import dateutil.parser
import datetime
from zoneinfo import ZoneInfo
from django.core.files.base import ContentFile
from django.db.models import Max, Min, Prefetch, Q
from django.db.models.functions import Greatest
from django.utils.timezone import is_naive, make_aware, now
from django.utils.translation import override
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from eventyay.celery_app import app
from eventyay.base.models import Channel, PollVote, Room, RoomView, User
from eventyay.base.models.event import Event, EventView
from eventyay.base.services.event import get_event_timezone
from eventyay.core.tasks import EventTask
from eventyay.features.analytics.graphs.report import ReportGenerator
from eventyay.features.analytics.graphs.utils import get_schedule, pretalx_uni18n
from eventyay.base.models.storage_model import StoredFile


def _parse_task_date_range(event, input_data, tz) -> tuple[datetime.datetime, datetime.datetime]:
    input_data = input_data if isinstance(input_data, dict) else {}
    begin = None
    end = None

    if input_data.get("begin"):
        try:
            begin = dateutil.parser.parse(str(input_data["begin"]))
        except (ValueError, TypeError):
            pass

    if input_data.get("end"):
        try:
            end = dateutil.parser.parse(str(input_data["end"]))
        except (ValueError, TypeError):
            pass

    if begin is None:
        begin = getattr(event, "date_from", None)
    if begin is None:
        begin = (
            RoomView.objects.filter(room__event=event, user__type=User.UserType.PERSON)
            .aggregate(min=Min("start"))["min"]
            or now()
        )
    if is_naive(begin):
        begin = make_aware(begin, tz)
    begin = begin.astimezone(tz)

    if end is None:
        end = getattr(event, "date_to", None)
    if end is None:
        end = (
            RoomView.objects.filter(room__event=event, user__type=User.UserType.PERSON)
            .aggregate(max=Greatest(Max("start"), Max("end")))["max"]
            or (begin + timedelta(days=1))
        )
    if is_naive(end):
        end = make_aware(end, tz)
    end = end.astimezone(tz)

    if end.astimezone(datetime.timezone.utc) < begin.astimezone(datetime.timezone.utc):
        begin, end = end, begin

    return begin, end


def _effective_view_end(
    start: datetime.datetime,
    end: datetime.datetime | None,
    max_duration: timedelta = timedelta(hours=3),
    reference_time: datetime.datetime | None = None,
) -> datetime.datetime:
    if end is not None:
        return end
    current_time = reference_time or now()
    effective = min(current_time, start + max_duration)
    return max(start, effective)


@app.task(base=EventTask)
def generate_report(event, input=None):
    with override(event.locale):
        try:
            cf = ReportGenerator(event, pdf_graphs=True).build(input)
        except Exception:
            # We first try to embed graphs directly into the PDF for best quality. Sometimes that fails,
            # then we fall back to PNG rendering of graphs
            cf = ReportGenerator(event, pdf_graphs=False).build(input)
        return cf.file.url


@app.task(base=EventTask)
def generate_attendee_list(event, input=None):
    io = BytesIO()

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Attendees")
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 30

    header = ["Internal ID", "External ID", "Name", "Permission traits"]
    ws.append(header)

    for u in event.user_set.all():
        ws.append(
            [
                str(u.pk),
                str(u.token_id) if u.token_id else "",
                u.profile.get("display_name") or "",
                ",".join(t for t in u.traits),
            ]
        )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=EventTask)
def generate_chat_history(event, input=None):
    channel = Channel.objects.get(pk=input.get("channel"))
    tz = get_event_timezone(event)
    io = BytesIO()

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Messages")
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 15
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 60

    header = ["Date", "Time", "Sender", "Content"]
    ws.append(header)

    for e in (
        channel.chat_events.filter(event_type="channel.message")
        .select_related("sender")
        .order_by("timestamp")
    ):
        if e.content.get("type") == "text":
            msg = e.content.get("body")
        elif e.content.get("type") == "files":
            msg = "\n".join(f.get("url") for f in e.content.get("files"))
            if e.content.get("body"):
                msg = e.content.get("body") + "\n" + msg
        else:
            msg = "<unknown message type>"
        ws.append(
            [
                e.timestamp.astimezone(tz).date(),
                e.timestamp.astimezone(tz).time(),
                e.sender.profile.get("display_name", ""),
                msg,
            ]
        )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=EventTask)
def generate_question_history(event, input=None):
    room = Room.objects.get(pk=input.get("room"))
    tz = get_event_timezone(event)
    io = BytesIO()

    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Questions")
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 15
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 40

    header = ["Date", "Time", "Content", "Votes", "Status"]
    ws.append(header)

    for e in room.questions.with_score().order_by("timestamp"):
        ws.append(
            [
                e.timestamp.astimezone(tz).date(),
                e.timestamp.astimezone(tz).time(),
                e.content,
                e.score,
                e.state,
            ]
        )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=EventTask)
def generate_room_views(event, input=None):
    wb = Workbook(write_only=True)
    io = BytesIO()
    tz = get_event_timezone(event)
    begin, end = _parse_task_date_range(event, input, tz)

    for room in event.rooms.all():
        types = [m["type"] for m in room.module_config]
        if any(
            t.startswith("livestream.")
            or t.startswith("chat.")
            or t.startswith("call.")
            for t in types
        ):
            name = re.sub("[^a-zA-Z0-9 ]", "", str(room.name))
            if room.deleted:
                name += " (deleted)"
            ws = wb.create_sheet(name)
            ws.freeze_panes = "A2"
            ws.column_dimensions["A"].width = 15
            ws.column_dimensions["B"].width = 15
            ws.column_dimensions["C"].width = 20
            ws.append(["Date", "Time", "Viewership (approx. unique users)"])

            day = begin
            while day.date() <= end.date():
                day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day.replace(hour=23, minute=59, second=59, microsecond=0)
                gds = max(begin, day_start)
                gde = min(end, day_end)
                if gds.astimezone(datetime.timezone.utc) >= gde.astimezone(datetime.timezone.utc):
                    day += timedelta(days=1)
                    continue

                gds_utc = gds.astimezone(datetime.timezone.utc)
                gde_utc = gde.astimezone(datetime.timezone.utc)
                views = (
                    room.views.filter(
                        Q(end__gte=gds)
                        | Q(end__isnull=True, start__gte=gds_utc - timedelta(hours=3)),
                        start__lte=gde,
                    )
                    .order_by()
                    .values("user", "start", "end")
                )

                adds = defaultdict(set)
                for v in views:
                    v_end = _effective_view_end(v["start"], v["end"])
                    if v_end < gds:
                        continue
                    v_start = max(gds, v["start"])
                    v_start_utc = v_start.astimezone(datetime.timezone.utc)
                    v_end_utc = v_end.astimezone(datetime.timezone.utc)
                    bucket = v_start_utc.replace(
                        second=0,
                        microsecond=0,
                        minute=v_start_utc.minute // 5 * 5,
                    )
                    while bucket <= gde_utc and bucket < v_end_utc:
                        adds[bucket].add(v["user"])
                        bucket += timedelta(minutes=5)

                t = gds_utc.replace(second=0, microsecond=0, minute=gds_utc.minute // 5 * 5)
                while t <= gde_utc:
                    ws.append(
                        [
                            t.astimezone(tz).date(),
                            t.astimezone(tz).time(),
                            len(adds[t]) if t in adds else "",
                        ]
                    )
                    t += timedelta(minutes=5)

                day += timedelta(days=1)

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=EventTask)
def generate_session_views(event, input=None):
    wb = Workbook(write_only=True)
    io = BytesIO()
    tz = get_event_timezone(event)
    begin, end = _parse_task_date_range(event, input, tz)
    begin_utc = begin.astimezone(datetime.timezone.utc)
    end_utc = end.astimezone(datetime.timezone.utc)
    ws = wb.create_sheet("Sessions")
    ws.append(
        [
            "Title",
            "Room",
            "Start date",
            "Start time",
            "End date",
            "End time",
            "Viewership (approx. unique users)",
        ]
    )

    room_cache = {r.pretalx_id: r for r in event.rooms.filter(deleted=False)}
    schedule = get_schedule(event, fail_silently=False)
    for talk in schedule.get("talks", []):
        talk_start = dateutil.parser.parse(talk["start"])
        talk_end = dateutil.parser.parse(talk["end"])
        if is_naive(talk_start):
            talk_start = make_aware(talk_start, tz)
        talk_start = talk_start.astimezone(tz)
        if is_naive(talk_end):
            talk_end = make_aware(talk_end, tz)
        talk_end = talk_end.astimezone(tz)
        talk_start_utc = talk_start.astimezone(datetime.timezone.utc)
        talk_end_utc = talk_end.astimezone(datetime.timezone.utc)
        if talk_start_utc > end_utc or talk_end_utc < begin_utc:
            continue

        try:
            viewers = (
                RoomView.objects.filter(room__pretalx_id=talk["room"])
                .filter(
                    Q(end__gte=talk_start)
                    | Q(end__isnull=True, start__gte=talk_start_utc - timedelta(hours=3)),
                    start__lte=talk_end,
                )
                .values("user")
                .distinct()
                .count()
            )

            ws.append(
                [
                    pretalx_uni18n(talk["title"]),
                    (
                        str(room_cache[talk["room"]].name)
                        if talk["room"] in room_cache and room_cache[talk["room"]].name
                        else "?"
                    ),
                    talk_start.astimezone(tz).date(),
                    talk_start.astimezone(tz).time(),
                    talk_end.astimezone(tz).date(),
                    talk_end.astimezone(tz).time(),
                    viewers,
                ]
            )
        except (ValueError, KeyError):  # e.g. pretalx_id not numeric
            pass

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=EventTask)
def generate_views(event, input=None):
    wb = Workbook(write_only=True)
    io = BytesIO()
    tz = get_event_timezone(event)
    begin, end = _parse_task_date_range(event, input, tz)
    begin_utc = begin.astimezone(datetime.timezone.utc)
    export_now = now()

    ws = wb.create_sheet("Room views")
    header = [
        "Room",
        "Start",
        "End",
        "User ID",
        "External ID",
        "User name",
    ]
    ws.append(header)
    rvq = (
        RoomView.objects.filter(
            Q(end__gte=begin)
            | Q(end__isnull=True, start__gte=begin_utc - timedelta(hours=3)),
            start__lte=end,
            room__event=event,
        )
        .select_related("room", "user")
        .order_by("start")
    )
    for v in rvq:
        u = v.user
        if u.profile.get("display_name"):
            v_end = _effective_view_end(v.start, v.end, reference_time=export_now)
            ws.append(
                [
                    str(v.room.name) if v.room and v.room.name else "",
                    f"{v.start.astimezone(tz):%d.%m.%Y %H:%M:%S}",
                    f"{v_end.astimezone(tz):%d.%m.%Y %H:%M:%S}",
                    str(u.pk),
                    u.token_id,
                    u.profile.get("display_name"),
                ]
            )

    ws = wb.create_sheet("Event views")
    header = [
        "Start",
        "End",
        "User ID",
        "External ID",
        "User name",
    ]
    ws.append(header)
    evq = (
        EventView.objects.filter(
            Q(end__gte=begin)
            | Q(end__isnull=True, start__gte=begin_utc - timedelta(hours=3)),
            start__lte=end,
            event=event,
        )
        .select_related("user")
        .order_by("start")
    )
    for v in evq:
        u = v.user
        if u.profile.get("display_name"):
            v_end = _effective_view_end(v.start, v.end, reference_time=export_now)
            ws.append(
                [
                    f"{v.start.astimezone(tz):%d.%m.%Y %H:%M:%S}",
                    f"{v_end.astimezone(tz):%d.%m.%Y %H:%M:%S}",
                    str(u.pk),
                    u.token_id,
                    u.profile.get("display_name"),
                ]
            )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=EventTask)
def generate_poll_history(event, input=None):
    room = Room.objects.get(pk=input.get("room"))
    io = BytesIO()

    wb = Workbook(write_only=True)

    for poll in room.polls.all():
        name = re.sub("[^a-zA-Z0-9 ]", "", poll.content)[:30]
        ws = wb.create_sheet(name)

        ws.freeze_panes = "A4"
        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 15
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 30

        ws.append([poll.content])
        ws.append([])

        header = ["Option", "Internal ID", "External ID", "Name"]
        ws.append(header)

        for v in (
            PollVote.objects.filter(option__poll=poll)
            .order_by("option__order", "option__id")
            .select_related("option", "sender")
        ):
            ws.append(
                [
                    v.option.content,
                    str(v.sender.pk),
                    str(v.sender.token_id) if v.sender.token_id else "",
                    v.sender.profile.get("display_name") or "",
                ]
            )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url


@app.task(base=EventTask)
def generate_attendee_session_list(event, input=None):
    io = BytesIO()
    tz = get_event_timezone(event)
    export_now = now()

    wb = Workbook(write_only=True)

    header = ["Internal ID", "External ID", "Name", "Duration (minutes)", "Permission traits"]

    room_cache = {r.pretalx_id: r for r in event.rooms.filter(deleted=False)}
    schedule = get_schedule(event, fail_silently=False)
    for talk in schedule.get("talks", []):
        name = re.sub("[^a-zA-Z0-9 ]", "", pretalx_uni18n(talk["title"]))[:30]
        ws = wb.create_sheet(name)
        ws.freeze_panes = "A4"
        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 30
        ws.column_dimensions["C"].width = 40
        ws.column_dimensions["D"].width = 20
        ws.column_dimensions["E"].width = 30

        talk_start = dateutil.parser.parse(talk["start"])
        talk_end = dateutil.parser.parse(talk["end"])
        if is_naive(talk_start):
            talk_start = make_aware(talk_start, tz)
        talk_start = talk_start.astimezone(tz)
        if is_naive(talk_end):
            talk_end = make_aware(talk_end, tz)
        talk_end = talk_end.astimezone(tz)

        talk_start_utc = talk_start.astimezone(datetime.timezone.utc)
        talk_end_utc = talk_end.astimezone(datetime.timezone.utc)

        ws.append([pretalx_uni18n(talk["title"])])
        ws.append(
            [
                str(room_cache[talk["room"]].name) if talk["room"] in room_cache and room_cache[talk["room"]].name else "?",
                talk_start.astimezone(tz).date(),
                talk_start.astimezone(tz).time(),
                talk_end.astimezone(tz).time(),
            ]
        )

        ws.append(header)

        try:
            qs = User.objects.filter(event=event).prefetch_related(
                Prefetch(
                    "views",
                    queryset=RoomView.objects.filter(
                        room__pretalx_id=talk["room"]
                    ).filter(
                        Q(end__gte=talk_start)
                        | Q(end__isnull=True, start__gte=talk_start_utc - timedelta(hours=3)),
                        start__lte=talk_end,
                    ),
                    to_attr="room_views_for_talk",
                )
            )
        except (ValueError, KeyError):  # e.g. pretalx_id not numeric
            continue

        for u in qs:
            if not u.room_views_for_talk:
                continue

            raw_intervals = []
            for v in u.room_views_for_talk:
                v_start_utc = v.start.astimezone(datetime.timezone.utc)
                v_eff_end = _effective_view_end(v.start, v.end, reference_time=export_now)
                v_end_utc = v_eff_end.astimezone(datetime.timezone.utc)

                iv_start = max(v_start_utc, talk_start_utc)
                iv_end = min(v_end_utc, talk_end_utc)
                if iv_start < iv_end:
                    raw_intervals.append((iv_start, iv_end))

            if not raw_intervals:
                continue

            raw_intervals.sort(key=lambda iv: iv[0])
            merged_intervals = [list(raw_intervals[0])]
            for s, e in raw_intervals[1:]:
                if s <= merged_intervals[-1][1]:
                    merged_intervals[-1][1] = max(merged_intervals[-1][1], e)
                else:
                    merged_intervals.append([s, e])

            sum_views = sum((e - s for s, e in merged_intervals), timedelta(seconds=0))
            minutes = int(sum_views.total_seconds() // 60)
            if minutes <= 0:
                continue

            ws.append(
                [
                    str(u.pk),
                    str(u.token_id) if u.token_id else "",
                    u.profile.get("display_name") or "",
                    minutes,
                    ",".join(t for t in u.traits),
                ]
            )

    wb.save(io)
    io.seek(0)

    sf = StoredFile.objects.create(
        event=event,
        date=now(),
        filename="report.xlsx",
        expires=now() + timedelta(hours=2),
        type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        public=True,
        user=None,
    )
    sf.file.save("report.xlsx", ContentFile(io.read()))
    return sf.file.url
