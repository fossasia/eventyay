from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponsePermanentRedirect
from django.utils.functional import cached_property
from django.views.generic import TemplateView
from django_context_decorator import context

from eventyay.common.views.mixins import EventPermissionRequired
from eventyay.base.models.submission import SubmissionStates
from eventyay.talk_rules.submission import are_featured_submissions_visible


def sneakpeek_redirect(request, *args, **kwargs):
    return HttpResponsePermanentRedirect(request.event.urls.featured)


class FeaturedView(EventPermissionRequired, TemplateView):
    template_name = 'agenda/featured.html'
    permission_required = 'base.list_featured_submission'

    def has_permission(self):
        """Gate on org "show featured" + schedule rules, not ``list_featured`` (orga always passes that)."""
        request = self.request
        user = getattr(request, 'user', None)
        if user is None:
            return False
        return are_featured_submissions_visible(user, request.event)

    @context
    def talks(self):
        return (
            self.request.event.submissions.filter(is_featured=True)
            .exclude(
                state__in=[
                    SubmissionStates.REJECTED,
                    SubmissionStates.CANCELED,
                    SubmissionStates.WITHDRAWN,
                    SubmissionStates.DELETED,
                ]
            )
            .select_related('event', 'event__organizer', 'submission_type')
            .prefetch_related('speakers')
            .order_by('title')
        )

    @context
    @cached_property
    def hide_visibility_warning(self):
        return are_featured_submissions_visible(AnonymousUser(), self.request.event)
