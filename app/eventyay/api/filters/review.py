import django_filters
from django_scopes import scope, scopes_disabled

from eventyay.base.models.auth import User
from eventyay.base.models.review import Review
from eventyay.base.models.submission import Submission
from eventyay.talk_rules.submission import get_reviewable_submissions


with scopes_disabled():

    class ReviewFilter(django_filters.FilterSet):
        submission = django_filters.ModelChoiceFilter(
            queryset=Submission.objects.none(),
            field_name='submission',
            to_field_name='code',
            help_text='Filter by submission code',
        )
        user = django_filters.ModelChoiceFilter(
            queryset=User.objects.none(),
            field_name='user',
            to_field_name='code',
            help_text='Filter by reviewer code',
        )
        speaker = django_filters.ModelChoiceFilter(
            queryset=User.objects.none(),
            field_name='submission__speakers',
            to_field_name='code',
            help_text='Filter by speaker code (for the submission being reviewed)',
        )

        def __init__(self, *args, event=None, **kwargs):
            request = kwargs.get('request')
            event = event or getattr(request, 'event', None)

            if event:
                with scope(event=event):
                    super().__init__(*args, **kwargs)
                    request = getattr(self, 'request', None) or request
                    user = getattr(request, 'user', None)
                    if not user or user.is_anonymous:
                        submissions = Submission.objects.none()
                        self.filters['submission'].queryset = submissions
                        self.filters['speaker'].queryset = User.objects.none()
                    else:
                        view = getattr(request, 'parser_context', {}).get('view', None) if request else None
                        visible = getattr(view, 'visible_submissions', None) if view else None
                        if visible is not None:
                            submissions = visible
                        else:
                            submissions = event.submissions.all().exclude(
                                speakers__in=[user]
                            )
                            submissions = get_reviewable_submissions(event, user, submissions)
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

                    if not user or user.is_anonymous:
                        self.filters['user'].queryset = User.objects.none()
                    else:
                        self.filters['user'].queryset = event.reviewers.all().distinct()
            else:
                with scopes_disabled():
                    super().__init__(*args, **kwargs)
                    has_explicit_qs = ('queryset' in kwargs) or (len(args) > 1 and args[1] is not None)
                    if not has_explicit_qs:
                        self.queryset = Review.objects.none()

        class Meta:
            model = Review
            fields = (
                'submission',
                'user',
                'speaker',
            )
