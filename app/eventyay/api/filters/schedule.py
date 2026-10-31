import django_filters
from django.db.models import Q
from django_scopes import scope, scopes_disabled

from eventyay.base.models.auth import User
from eventyay.base.models.room import Room
from eventyay.base.models.schedule import Schedule
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.submission import Submission


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
            if not value:
                return queryset
            if value.strip().lower() == 'wip':
                request = getattr(self, 'request', None)
                event = getattr(request, 'event', None)
                is_orga = bool(
                    request
                    and getattr(request, 'user', None)
                    and event
                    and request.user.has_perm('base.orga_view_schedule', event)
                )
                if not is_orga:
                    return queryset.none()
                return queryset.filter(schedule__version__isnull=True)
            return queryset.filter(schedule__version__iexact=value.strip())

        def __init__(self, *args, event=None, **kwargs):
            super().__init__(*args, **kwargs)
            request = getattr(self, 'request', None) or kwargs.get('request')
            event = event or getattr(request, 'event', None)
            if event:
                with scope(event=event):
                    self.filters['schedule'].queryset = event.schedules.all()
                    self.filters['submission'].queryset = event.submissions.all()
                    self.filters['room'].queryset = event.rooms.all()

                    is_orga = bool(
                        request
                        and getattr(request, 'user', None)
                        and request.user.has_perm('base.orga_view_schedule', event)
                    )
                    if is_orga:
                        self.filters['speaker'].queryset = User.objects.filter(
                            submissions__in=event.submissions.all()
                        ).distinct()
                    else:
                        visible_submissions = event.submissions.filter(
                            Q(slots__is_visible=True, slots__schedule__version__isnull=False)
                            & (Q(slots__room__isnull=True) | Q(slots__room__deleted=False))
                        )
                        self.filters['speaker'].queryset = User.objects.filter(
                            submissions__in=visible_submissions
                        ).distinct()

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
