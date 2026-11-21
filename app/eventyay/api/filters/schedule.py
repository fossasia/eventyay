import django_filters
from django_scopes import scope, scopes_disabled

from eventyay.base.models.auth import User
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
        if organizer := getattr(event, 'organizer', getattr(event, 'organiser', None)):
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
        speaker = django_filters.ModelChoiceFilter(
            queryset=User.objects.none(),
            field_name='submission__speakers',
            to_field_name='code',
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
            is_orga = has_orga_schedule_permission(request, event) or request is None
            if val.lower() == 'wip':
                if is_orga:
                    return queryset.filter(schedule__version__isnull=True)
                return queryset.none()
            if not is_orga:
                current_ver = (
                    (event.current_schedule.version or '').lower()
                    if event and event.current_schedule
                    else None
                )
                if not current_ver or val.lower() != current_ver:
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
                        # request is None permits direct instantiation (e.g. scripts/unit tests) without an HTTP request
                        self.filters['schedule'].queryset = self.event.schedules.all()
                        self.filters['submission'].queryset = self.event.submissions.all()
                        self.filters['speaker'].queryset = User.objects.filter(
                            submissions__event=self.event
                        ).distinct()
                        self.filters['room'].queryset = self.event.rooms.all()
                    else:
                        self.filters['schedule'].queryset = (
                            self.event.schedules.filter(pk=self.event.current_schedule.pk)
                            if self.event.current_schedule
                            else self.event.schedules.none()
                        )
                        self.filters['submission'].queryset = (
                            self.event.submissions.filter(
                                slots__is_visible=True,
                                slots__schedule=self.event.current_schedule,
                            ).distinct()
                            if self.event.current_schedule
                            else self.event.submissions.none()
                        )
                        self.filters['speaker'].queryset = (
                            User.objects.filter(
                                submissions__slots__schedule=self.event.current_schedule,
                                submissions__slots__is_visible=True,
                            ).distinct()
                            if self.event.current_schedule
                            else User.objects.none()
                        )
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
                'speaker',
                'room',
                'is_visible',
            ]
