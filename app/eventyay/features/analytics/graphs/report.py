import io
import tempfile
from datetime import timedelta

import dateutil.parser
import datetime
from zoneinfo import ZoneInfo
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    Max,
    Min,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest, Least
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.timezone import is_naive, make_aware, now
from django.utils.translation import gettext as _
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Table,
    TableStyle,
)

from eventyay.base.models import Channel, ChatEvent, Room, User
from eventyay.base.models.room import RoomView
from eventyay.base.services.event import get_event_timezone
from eventyay.features.analytics.graphs.utils import PdfImage, get_schedule, median_value, pretalx_uni18n
from eventyay.features.analytics.graphs.views import build_room_view_fig
from eventyay.base.models.storage_model import StoredFile


class ReportGenerator:
    def __init__(self, event, pdf_graphs=True, input=None):
        self.event = event
        self.pdf_graphs = pdf_graphs
        self.input = input or {}

    def build(self, input=None):
        if input is not None:
            self.input = input or {}
        _ = self.schedule

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            doc = self.get_doc_template()(
                f.name,
                pagesize=self.pagesize,
                leftMargin=15 * mm,
                rightMargin=15 * mm,
                topMargin=20 * mm,
                bottomMargin=15 * mm,
            )
            doc.addPageTemplates(
                [
                    PageTemplate(
                        id="All",
                        frames=self.get_frames(doc),
                        onPage=self.on_page,
                        pagesize=self.pagesize,
                    )
                ]
            )
            doc.build(self.get_story())
            f.seek(0)
            sf = StoredFile.objects.create(
                event=self.event,
                date=now(),
                expires=now() + timedelta(hours=2),
                filename="report.pdf",
                type="application/pdf",
                public=True,
                user=None,
            )
            sf.file.save("report.pdf", ContentFile(f.read()))
            return sf

    @property
    def pagesize(self):
        from reportlab.lib import pagesizes

        return pagesizes.portrait(pagesizes.A4)

    def get_doc_template(self):
        from reportlab.platypus import BaseDocTemplate

        return BaseDocTemplate

    def get_frames(self, doc):
        from reportlab.platypus import Frame

        self.frame = Frame(
            doc.leftMargin,
            doc.bottomMargin,
            doc.width,
            doc.height,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="normal",
        )
        return [self.frame]

    @cached_property
    def stylesheet(self):
        from reportlab.lib.styles import getSampleStyleSheet

        style = getSampleStyleSheet()
        return style

    def on_page(self, canvas, doc):
        canvas.saveState()
        self.page_footer(canvas, doc)
        self.page_header(canvas, doc)
        canvas.restoreState()

    def page_footer(self, canvas, doc):
        from reportlab.lib.units import mm

        canvas.setFont("Helvetica", 8)
        # canvas.drawString(15 * mm, 10 * mm, _("Page %d") % (doc.page,))
        canvas.drawRightString(
            self.pagesize[0] - 15 * mm,
            10 * mm,
            now().astimezone(self.tz).strftime("%d.%m.%Y %H:%M:%S"),
        )

    def get_right_header_string(self):
        return "eventyay"

    def get_left_header_string(self):
        return str(self.event.name)

    def page_header(self, canvas, doc):
        from reportlab.lib.units import mm

        canvas.setFont("Helvetica", 10)
        canvas.drawString(
            15 * mm, self.pagesize[1] - 15 * mm, self.get_left_header_string()
        )
        canvas.drawRightString(
            self.pagesize[0] - 15 * mm,
            self.pagesize[1] - 15 * mm,
            self.get_right_header_string(),
        )
        canvas.setStrokeColorRGB(0, 0, 0)
        canvas.line(
            15 * mm,
            self.pagesize[1] - 17 * mm,
            self.pagesize[0] - 15 * mm,
            self.pagesize[1] - 17 * mm,
        )

    @cached_property
    def schedule(self):
        return get_schedule(self.event)

    @cached_property
    def tz(self) -> ZoneInfo:
        return get_event_timezone(self.event)

    @cached_property
    def date_begin(self):
        begin = None
        inp = getattr(self, "input", None) or {}
        if inp.get("begin"):
            try:
                begin = dateutil.parser.parse(str(inp.get("begin")))
            except (ValueError, TypeError):
                pass

        if begin is None:
            begin = getattr(self.event, "date_from", None)
        if begin is None:
            begin = (
                RoomView.objects.filter(
                    room__event=self.event, user__type=User.UserType.PERSON
                ).aggregate(min=Min("start"))["min"]
                or now()
            )

        if is_naive(begin):
            begin = make_aware(begin, self.tz)
        return begin.astimezone(self.tz)

    @cached_property
    def date_end(self):
        end = None
        inp = getattr(self, "input", None) or {}
        if inp.get("end"):
            try:
                end = dateutil.parser.parse(str(inp.get("end")))
            except (ValueError, TypeError):
                pass

        if end is None:
            end = getattr(self.event, "date_to", None)
        if end is None:
            end = (
                RoomView.objects.filter(
                    room__event=self.event, user__type=User.UserType.PERSON
                ).aggregate(max=Greatest(Max("start"), Max("end")))["max"]
                or (self.date_begin + timedelta(days=1))
            )

        if is_naive(end):
            end = make_aware(end, self.tz)
        end = end.astimezone(self.tz)
        if end.astimezone(datetime.timezone.utc) < self.date_begin.astimezone(datetime.timezone.utc):
            end = self.date_begin + timedelta(days=1)
        return end

    def get_story(self):
        s = [
            Paragraph(str(self.event.name), self.stylesheet["Heading1"]),
        ]
        s += self.global_sums()

        for room in self.event.rooms.all():
            types = [m["type"] for m in room.module_config]
            if any(
                t.startswith("livestream.")
                or t.startswith("chat.")
                or t.startswith("call.")
                for t in types
            ):
                s += self.story_for_room(room)

        return s

    @cached_property
    def day_whitelist(self):
        # currently not in use
        if "days" not in self.input:
            return None
        return [dateutil.parser.parse(d).date() for d in self.input.get("days")]

    def story_for_room(self, room: Room):
        s = [
            PageBreak(),
            Paragraph(
                str(room.name) + (" (deleted)" if room.deleted else ""),
                self.stylesheet["Heading2"],
            ),
            # todo: average time spent per user
        ]

        tstyledata = [
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]

        date_begin_utc = self.date_begin.astimezone(datetime.timezone.utc)
        rvqs = RoomView.objects.filter(
            Q(end__gte=self.date_begin)
            | Q(end__isnull=True, start__gte=date_begin_utc - timedelta(hours=3)),
            start__lte=self.date_end,
        )

        report_now = now()
        clipped_duration = Greatest(
            ExpressionWrapper(
                Least(
                    Coalesce(
                        "end",
                        Least(
                            Value(report_now, output_field=models.DateTimeField()),
                            ExpressionWrapper(
                                F("start") + timedelta(hours=3),
                                output_field=models.DateTimeField(),
                            ),
                        ),
                    ),
                    Value(self.date_end, output_field=models.DateTimeField()),
                )
                - Greatest(
                    F("start"),
                    Value(self.date_begin, output_field=models.DateTimeField()),
                ),
                output_field=models.DurationField(),
            ),
            Value(timedelta(0), output_field=models.DurationField()),
        )

        unique_users = rvqs.filter(room=room, user__type=User.UserType.PERSON).values(
            "user"
        )
        users_with_duration = User.objects.filter(
            id__in=unique_users,
            type=User.UserType.PERSON,
        ).annotate(
            total_duration=Subquery(
                rvqs.filter(
                    user=OuterRef("pk"),
                    room=room,
                )
                .values("room")
                .order_by()
                .annotate(
                    total_duration=Sum(clipped_duration)
                )
                .values("total_duration")
            )
        )
        aggs = users_with_duration.aggregate(a=Avg("total_duration"))

        tdata = [
            [
                _("Total number of unique viewers"),
                str(unique_users.distinct().count()),
            ],
            [_("Average time spent in room"), str(aggs["a"] or 0)],
            [
                _("Median time spent in room"),
                str(median_value(users_with_duration, "total_duration") or 0),
            ],
        ]
        if Channel.objects.filter(room=room).exists():
            tdata += [
                [
                    _("Number of chat messages"),
                    str(
                        ChatEvent.objects.filter(
                            timestamp__gte=self.date_begin,
                            timestamp__lte=self.date_end,
                            event_type="channel.message",
                            channel__room=room,
                        ).count()
                    ),
                ],
                [
                    _("Number of users who sent chat messages"),
                    str(
                        ChatEvent.objects.filter(
                            timestamp__gte=self.date_begin,
                            timestamp__lte=self.date_end,
                            event_type="channel.message",
                            channel__room=room,
                        )
                        .values("sender")
                        .distinct()
                        .count()
                    ),
                ],
            ]

        w = self.pagesize[0] - 30 * mm
        colwidths = [0.8 * w, 0.2 * w]
        table = Table(tdata, colWidths=colwidths, repeatRows=1)
        table.setStyle(TableStyle(tstyledata))
        s.append(table)

        day = self.date_begin
        while day.date() <= self.date_end.date():
            if self.day_whitelist is not None and day.date() not in self.day_whitelist:
                day += timedelta(days=1)
                continue
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=0)
            gds = max(self.date_begin, day_start)
            gde = min(self.date_end, day_end)
            if gds.astimezone(datetime.timezone.utc) >= gde.astimezone(datetime.timezone.utc):
                day += timedelta(days=1)
                continue
            fig = Figure(figsize=(7, 4))
            build_room_view_fig(fig, room, gds, gde, self.tz)
            s.append(
                KeepTogether(
                    [
                        Paragraph(
                            date_format(day, "SHORT_DATE_FORMAT"),
                            self.stylesheet["Heading3"],
                        ),
                        self._graph(fig),
                    ]
                )
            )
            day += timedelta(days=1)

        if room.pretalx_id and self.schedule:
            w = self.pagesize[0] - 30 * mm
            colwidths = [0.4 * w, 0.25 * w, 0.25 * w, 0.1 * w]
            tdata = []
            tstyledata = [
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
            date_begin_utc = self.date_begin.astimezone(datetime.timezone.utc)
            date_end_utc = self.date_end.astimezone(datetime.timezone.utc)
            for talk in self.schedule["talks"]:
                if str(talk["room"]) != str(room.pretalx_id):
                    continue
                talk_start = dateutil.parser.parse(talk["start"])
                talk_end = dateutil.parser.parse(talk["end"])
                if is_naive(talk_start):
                    talk_start = make_aware(talk_start, self.tz)
                talk_start = talk_start.astimezone(self.tz)
                if is_naive(talk_end):
                    talk_end = make_aware(talk_end, self.tz)
                talk_end = talk_end.astimezone(self.tz)
                talk_start_utc = talk_start.astimezone(datetime.timezone.utc)
                talk_end_utc = talk_end.astimezone(datetime.timezone.utc)
                if talk_start_utc > date_end_utc or talk_end_utc < date_begin_utc:
                    continue

                viewers = (
                    RoomView.objects.filter(room=room, user__type=User.UserType.PERSON)
                    .filter(
                        Q(end__gte=talk_start)
                        | Q(end__isnull=True, start__gte=talk_start_utc - timedelta(hours=3)),
                        start__lte=talk_end,
                    )
                    .values("user")
                    .distinct()
                    .count()
                )

                tdata.append(
                    [
                        Paragraph(
                            pretalx_uni18n(talk["title"], self.event.locale),
                            self.stylesheet["Normal"],
                        ),
                        Paragraph(
                            date_format(talk_start, "SHORT_DATETIME_FORMAT"),
                            self.stylesheet["Normal"],
                        ),
                        Paragraph(
                            date_format(talk_end, "SHORT_DATETIME_FORMAT"),
                            self.stylesheet["Normal"],
                        ),
                        str(viewers),
                    ]
                )

            if tdata:
                s.append(
                    Paragraph(
                        _("Unique viewers by session"),
                        self.stylesheet["Heading3"],
                    )
                )
                tdata.insert(0, [_("Session"), _("Start"), _("End"), _("Viewers")])
                table = Table(tdata, colWidths=colwidths, repeatRows=1)
                table.setStyle(TableStyle(tstyledata))
                s.append(table)

        return s

    def global_sums(self):
        s = []
        tstyledata = [
            ("ALIGN", (0, 0), (-1, 0), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]

        tdata = [
            [
                _("Report timeframe start"),
                date_format(self.date_begin, "SHORT_DATETIME_FORMAT"),
            ],
            [
                _("Report timeframe end"),
                date_format(self.date_end, "SHORT_DATETIME_FORMAT"),
            ],
            [_("Number of users (total)"), str(self.event.user_set.count())],
            [
                _("Users with authenticated access (total)"),
                str(
                    self.event.user_set.filter(
                        token_id__isnull=False, type=User.UserType.PERSON
                    ).count()
                ),
            ],
            [
                _(
                    "Number of chat messages in streams and chat channels (in timeframe)"
                ),
                str(
                    ChatEvent.objects.filter(
                        channel__event=self.event,
                        event_type="channel.message",
                        channel__room__isnull=False,
                        timestamp__gte=self.date_begin,
                        timestamp__lte=self.date_end,
                    ).count()
                ),
            ],
            [
                _("Number of direct message channels (total)"),
                str(
                    Channel.objects.filter(event=self.event, room__isnull=True).count()
                ),
            ],
            [
                _("Number of chat messages in direct messages (in timeframe)"),
                str(
                    ChatEvent.objects.filter(
                        channel__event=self.event,
                        event_type="channel.message",
                        channel__room__isnull=True,
                        timestamp__gte=self.date_begin,
                        timestamp__lte=self.date_end,
                    ).count()
                ),
            ],
            [
                _("Number of 1:1 call attempts (in timeframe)"),
                str(
                    ChatEvent.objects.filter(
                        channel__event=self.event,
                        event_type="channel.message",
                        channel__room__isnull=True,
                        content__type="call",
                        timestamp__gte=self.date_begin,
                        timestamp__lte=self.date_end,
                    ).count()
                ),
            ],
        ]

        w = self.pagesize[0] - 30 * mm
        colwidths = [0.8 * w, 0.2 * w]
        table = Table(tdata, colWidths=colwidths, repeatRows=1)
        table.setStyle(TableStyle(tstyledata))
        s.append(table)

        day = self.date_begin
        while day.date() <= self.date_end.date():
            if self.day_whitelist is not None and day.date() not in self.day_whitelist:
                day += timedelta(days=1)
                continue
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=0)
            gds = max(self.date_begin, day_start)
            gde = min(self.date_end, day_end)
            if gds.astimezone(datetime.timezone.utc) >= gde.astimezone(datetime.timezone.utc):
                day += timedelta(days=1)
                continue
            fig = Figure(figsize=(7, 4))
            build_room_view_fig(fig, self.event, gds, gde, self.tz)
            s.append(
                KeepTogether(
                    [
                        Paragraph(
                            date_format(day, "SHORT_DATE_FORMAT"),
                            self.stylesheet["Heading3"],
                        ),
                        Paragraph(
                            "Counts the number of people currently either in a video room or live stream room."
                            " Does not count people only in text channels.",
                            self.stylesheet["Normal"],
                        ),
                        self._graph(fig),
                    ]
                )
            )
            day += timedelta(days=1)

        return s

    def _graph(self, fig):
        if self.pdf_graphs:
            imgdata = io.BytesIO()
            fig.savefig(imgdata, format="PDF")
            return PdfImage(imgdata)
        else:
            imgdata = io.BytesIO()
            fig.savefig(imgdata, dpi=600, format="PNG")
            imgdata.seek(0)
            w = self.pagesize[0] - 30 * mm
            return Image(
                imgdata,
                width=w,
                height=fig.get_figheight() / fig.get_figwidth() * w,
            )
