import django_filters
from django_scopes import scopes_disabled

from eventyay.base.models.auth import User
from eventyay.base.models.submission import Submission
from eventyay.base.models.review import Review

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

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            event = getattr(kwargs.get("request"), "event", None)
            if event:
                submissions = event.submissions.all()
                self.filters["submission"].queryset = submissions
                self.filters["user"].queryset = event.reviewers.all()
                self.filters["speaker"].queryset = User.objects.filter(
                    submissions__in=submissions
                )

        class Meta:
            model = Review
            fields = (
                "submission",
                "user",
                "speaker",
            )
