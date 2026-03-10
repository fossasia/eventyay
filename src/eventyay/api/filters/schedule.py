import django_filters
from django_scopes import scopes_disabled

from eventyay.base.models.auth import User
from eventyay.base.models.schedule import Schedule
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.room import Room
from eventyay.base.models.submission import Submission

with scopes_disabled():

    class TalkSlotFilter(django_filters.FilterSet):
        submission = django_filters.ModelChoiceFilter(
            queryset=Submission.objects.none(),
            field_name="submission",
            to_field_name="code",
        )
        schedule = django_filters.ModelChoiceFilter(
            queryset=Schedule.objects.none(),
            field_name="schedule",
        )
        schedule_version = django_filters.ModelChoiceFilter(
            queryset=Schedule.objects.none(),
            field_name="schedule__version",
            lookup_expr="iexact",
        )
        speaker = django_filters.ModelChoiceFilter(
            queryset=User.objects.none(),
            field_name="submission__speakers",
            to_field_name="code",
        )
        room = django_filters.ModelChoiceFilter(
            queryset=Room.objects.none(),
            field_name="room",
        )

        def __init__(self, *args, event=None, **kwargs):
            super().__init__(*args, **kwargs)
            event = getattr(kwargs.get("request"), "event", None)
            if event:
                for field in ("schedule", "schedule_version"):
                    self.filters[field].queryset = event.schedules.all()
                self.filters["submission"].queryset = event.submissions.all()
                self.filters["room"].queryset = event.rooms.all()

        class Meta:
            model = TalkSlot
            fields = [
                "submission",
                "schedule",
                "schedule_version",
                "speaker",
                "room",
                "is_visible",
            ]
