import django_filters
from django_scopes import scope, scopes_disabled

from eventyay.base.models.auth import User
from eventyay.base.models.review import Review
from eventyay.base.models.submission import Submission
from eventyay.talk_rules.submission import get_reviewable_submissions


def has_orga_review_permission(request, event):
    if not request or not event:
        return False
    user = getattr(request, "user", None)
    if user and hasattr(user, "has_perm") and user.has_perm("base.orga_update_submission", event):
        return True
    auth = getattr(request, "auth", None)
    if auth and hasattr(auth, "get_event_permission_set"):
        organizer = getattr(event, "organizer", None)
        if organizer:
            permset = auth.get_event_permission_set(organizer, event)
            if "can_change_submissions" in permset:
                return True
    return False


def get_review_visible_submissions(event, user):
    if not event or not user or user.is_anonymous:
        return Submission.objects.none()
    submissions = event.submissions.all().exclude(speakers__in=[user])
    return get_reviewable_submissions(event, user, submissions)


with scopes_disabled():

    class ReviewFilter(django_filters.FilterSet):
        submission = django_filters.ModelChoiceFilter(
            queryset=Submission.objects.none(),
            field_name="submission",
            to_field_name="code",
            help_text="Filter by submission code",
        )
        user = django_filters.ModelChoiceFilter(
            queryset=User.objects.none(),
            field_name="user",
            to_field_name="code",
            help_text="Filter by reviewer code",
        )
        speaker = django_filters.ModelChoiceFilter(
            queryset=User.objects.none(),
            field_name="submission__speakers",
            to_field_name="code",
            help_text="Filter by speaker code (for the submission being reviewed)",
        )

        def __init__(self, *args, event=None, **kwargs):
            request = kwargs.get("request") or getattr(self, "request", None)
            self.event = event or getattr(request, "event", None)
            if self.event:
                with scope(event=self.event):
                    super().__init__(*args, **kwargs)
                    user = getattr(request, "user", None)
                    if has_orga_review_permission(request, self.event):
                        submissions = self.event.submissions.all()
                    elif user and not user.is_anonymous:
                        submissions = get_review_visible_submissions(self.event, user)
                    elif request is None:
                        # Direct instantiation without HTTP request (e.g. tests) gets all event submissions
                        submissions = self.event.submissions.all()
                    else:
                        submissions = self.event.submissions.none()

                    self.filters["submission"].queryset = submissions
                    self.filters["user"].queryset = self.event.reviewers.all()
                    self.filters["speaker"].queryset = User.objects.filter(
                        submissions__in=submissions
                    ).distinct()
            else:
                with scopes_disabled():
                    super().__init__(*args, **kwargs)

        class Meta:
            model = Review
            fields = (
                "submission",
                "user",
                "speaker",
            )
