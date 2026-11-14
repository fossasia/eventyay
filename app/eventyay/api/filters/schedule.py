import django_filters
from django_scopes import scope, scopes_disabled

from eventyay.base.models.room import Room
from eventyay.base.models.schedule import Schedule
from eventyay.base.models.slot import TalkSlot
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
        schedule_version = django_filters.CharFilter(
            method="filter_schedule_version",
        )
        room = django_filters.ModelChoiceFilter(
            queryset=Room.objects.none(),
            field_name="room",
        )

        def filter_schedule_version(self, queryset, name, value):
            if not value:
                return queryset
            val = str(value).strip()
            request = getattr(self, "request", None)
            event = getattr(request, "event", None) or getattr(self, "event", None)
            if val.lower() == "wip":
                is_orga = False
                if request and getattr(request, "user", None) and event:
                    if hasattr(request.user, "has_perm") and request.user.has_perm("base.orga_view_schedule", event):
                        is_orga = True
                if not is_orga and request and getattr(request, "auth", None) and event:
                    auth = request.auth
                    if hasattr(auth, "get_event_permission_set"):
                        permset = auth.get_event_permission_set(event.organizer, event)
                        if "can_change_submissions" in permset:
                            is_orga = True
                if is_orga:
                    return queryset.filter(schedule__version__isnull=True)
                return queryset.none()
            return queryset.filter(schedule__version__iexact=val)

        def __init__(self, *args, event=None, **kwargs):
            super().__init__(*args, **kwargs)
            request = kwargs.get("request")
            event = event or getattr(request, "event", None)
            if event:
                with scope(event=event):
                    self.filters["schedule"].queryset = event.schedules.all()
                    self.filters["submission"].queryset = event.submissions.all()
                    self.filters["room"].queryset = event.rooms.all()

        class Meta:
            model = TalkSlot
            fields = [
                "submission",
                "schedule",
                "schedule_version",
                "room",
                "is_visible",
            ]
