import django_filters
from django.db.models import Q
from django_scopes import scope, scopes_disabled

from eventyay.base.models.auth import User
from eventyay.base.models.room import Room
from eventyay.base.models.schedule import Schedule
from eventyay.base.models.slot import TalkSlot
from eventyay.base.models.submission import Submission
from eventyay.talk_rules.tracks import apply_track_limit, user_has_track_limits


def check_is_orga(request, event, view=None):
    if view is None and request:
        view = getattr(request, 'parser_context', {}).get('view', None)
    # Check view.__dict__ directly so we only reuse is_orga if the @cached_property
    # has already been evaluated on this view instance. Accessing view.is_orga before
    # evaluation would re-enter check_is_orga recursively.
    if view and 'is_orga' in getattr(view, '__dict__', {}):
        return bool(view.is_orga)
    if not (request and getattr(request, 'user', None) and event):
        return False
    if hasattr(request.user, 'has_perm') and request.user.has_perm('base.orga_view_schedule', event):
        return True
    auth = getattr(request, 'auth', None)
    if auth and hasattr(auth, 'get_event_permission_set'):
        permset = auth.get_event_permission_set(event.organizer, event)
        if 'can_change_submissions' in permset:
            return True
    eventpermset = getattr(request, 'eventpermset', set())
    return 'can_change_submissions' in eventpermset


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
            if value.strip().lower() == 'wip':
                is_orga = getattr(self, 'is_orga', None)
                if is_orga is None:
                    request = getattr(self, 'request', None)
                    event = getattr(request, 'event', None)
                    view = getattr(request, 'parser_context', {}).get('view', None) if request else None
                    is_orga = check_is_orga(request, event, view)
                if not is_orga:
                    return queryset.none()
                return queryset.filter(schedule__version__isnull=True)
            return queryset.filter(schedule__version__iexact=value.strip())

        def __init__(self, *args, event=None, **kwargs):
            filter_fields = set(self.base_filters.keys())
            if 'data' in kwargs and kwargs['data'] is not None:
                data = kwargs['data']
                if hasattr(data, 'copy'):
                    cleaned_data = data.copy()
                else:
                    cleaned_data = dict(data)
                for key in list(cleaned_data.keys()):
                    if key in filter_fields and not str(cleaned_data[key]).strip():
                        cleaned_data.pop(key)
                kwargs['data'] = cleaned_data
            elif args and args[0] is not None:
                data = args[0]
                if hasattr(data, 'copy'):
                    cleaned_data = data.copy()
                else:
                    cleaned_data = dict(data)
                for key in list(cleaned_data.keys()):
                    if key in filter_fields and not str(cleaned_data[key]).strip():
                        cleaned_data.pop(key)
                args = (cleaned_data,) + args[1:]

            request = kwargs.get('request')
            event = event or getattr(request, 'event', None)

            if event:
                with scope(event=event):
                    super().__init__(*args, **kwargs)
                    request = getattr(self, 'request', None) or request
                    user = getattr(request, 'user', None)
                    view = getattr(request, 'parser_context', {}).get('view', None) if request else None
                    is_orga = check_is_orga(request, event, view)
                    self.is_orga = is_orga
                    if is_orga:
                        submissions = event.submissions.all()
                        self.filters['schedule'].queryset = event.schedules.all()
                        self.filters['room'].queryset = event.rooms.all()
                    else:
                        submissions = event.submissions.filter(
                            Q(slots__is_visible=True, slots__schedule__version__isnull=False)
                            & (Q(slots__room__isnull=True) | Q(slots__room__deleted=False))
                        ).distinct()
                        self.filters['schedule'].queryset = event.schedules.filter(version__isnull=False)
                        self.filters['room'].queryset = event.rooms.filter(deleted=False)

                    if user and user_has_track_limits(event, user):
                        submissions = apply_track_limit(submissions, event, user)

                    self.filters['submission'].queryset = submissions.distinct()
                    from eventyay.talk_rules.orga import (
                        can_view_speaker_names,
                        enforces_hide_speaker_names,
                        is_reviewer_only_for_event,
                    )
                    if isinstance(user, User) and (
                        enforces_hide_speaker_names(user, event)
                        or (
                            is_reviewer_only_for_event(user, event)
                            and not can_view_speaker_names(user, event)
                        )
                    ):
                        self.filters['speaker'].queryset = User.objects.none()
                    else:
                        self.filters['speaker'].queryset = User.objects.filter(
                            pk__in=User.objects.filter(submissions__in=submissions).values('pk')
                        )
            else:
                with scopes_disabled():
                    super().__init__(*args, **kwargs)
                    has_explicit_qs = ('queryset' in kwargs) or (len(args) > 1 and args[1] is not None)
                    if not has_explicit_qs:
                        self.queryset = TalkSlot.objects.none()

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
