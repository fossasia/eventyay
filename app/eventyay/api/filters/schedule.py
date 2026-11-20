import django_filters
from django_scopes import scope, scopes_disabled

from eventyay.base.models.room import Room
from eventyay.base.models.schedule import Schedule
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.submission import Submission


def has_orga_schedule_permission(request, event):
    if not request or not event:
        return False
    user = getattr(request, 'user', None)
    if user and hasattr(user, 'has_perm') and user.has_perm('base.release_schedule', event):
        return True
    auth = getattr(request, 'auth', None)
    if auth and hasattr(auth, 'get_event_permission_set'):
        organizer = getattr(event, 'organizer', None)
        if organizer:
            permset = auth.get_event_permission_set(organizer, event)
            if 'can_change_submissions' in permset:
                return True
    return False


with scopes_disabled():

    class TalkSlotFilter(django_filters.FilterSet):
        submission = django_filters.ModelChoiceFilter(
            queryset=Submission.objects.none(),
            field_name='submission',
            to_field_name='code',
        )
        schedule = django_filters.ModelChoiceFilter(
            queryset=Schedule.objects.none(),
            field_name='schedule',
        )
        schedule_version = django_filters.CharFilter(
            method='filter_schedule_version',
        )
        room = django_filters.ModelChoiceFilter(
            queryset=Room.objects.none(),
            field_name='room',
        )

        def filter_schedule_version(self, queryset, name, value):
            if not value or not str(value).strip():
                return queryset
            val = str(value).strip()
            request = getattr(self, 'request', None)
            event = getattr(self, 'event', None) or getattr(request, 'event', None)
            if val.lower() == 'wip':
                if has_orga_schedule_permission(request, event):
                    return queryset.filter(schedule__version__isnull=True)
                return queryset.none()
            return queryset.filter(schedule__version__iexact=val)

        def __init__(self, *args, event=None, **kwargs):
            request = kwargs.get('request') or getattr(self, 'request', None)
            self.event = event or getattr(request, 'event', None)
            if self.event:
                with scope(event=self.event):
                    super().__init__(*args, **kwargs)
                    is_orga = has_orga_schedule_permission(request, self.event)

                    if is_orga or request is None:
                        # Full querysets are granted to organizers, or when instantiated
                        # directly without an HTTP request (e.g. scripts/unit tests).
                        # In real API calls, DRF always passes request, so non-organizers
                        # always take the scoped branch below.
                        self.filters['schedule'].queryset = self.event.schedules.all()
                        self.filters['submission'].queryset = self.event.submissions.all()
                        self.filters['room'].queryset = self.event.rooms.all()
                    else:
                        self.filters['schedule'].queryset = self.event.schedules.filter(version__isnull=False)
                        self.filters['submission'].queryset = self.event.submissions.filter(
                            slots__is_visible=True, slots__schedule__version__isnull=False
                        ).distinct()
                        self.filters['room'].queryset = self.event.rooms.filter(deleted=False)
            else:
                with scopes_disabled():
                    super().__init__(*args, **kwargs)

        class Meta:
            model = TalkSlot
            fields = [
                'submission',
                'schedule',
                'schedule_version',
                'room',
                'is_visible',
            ]
