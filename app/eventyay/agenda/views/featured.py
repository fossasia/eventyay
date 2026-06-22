from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponsePermanentRedirect
from django.utils.functional import cached_property
from django.views.generic import TemplateView
from django_context_decorator import context

from eventyay.agenda.views.schedule import ScheduleMixin
from eventyay.agenda.views.utils import (
    build_featured_schedule_json,
    build_featured_schedule_meta_json,
)
from eventyay.common.views.mixins import EventPermissionRequired
from eventyay.talk_rules.submission import are_featured_submissions_visible, event_has_featured_submissions


def sneakpeek_redirect(request, *args, **kwargs):
    return HttpResponsePermanentRedirect(request.event.urls.featured)


class FeaturedView(EventPermissionRequired, ScheduleMixin, TemplateView):
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
    def schedule_data_json(self):
        return build_featured_schedule_json(self.request)

    @context
    def has_featured_submissions(self):
        return event_has_featured_submissions(self.request.event)

    @context
    @cached_property
    def hide_visibility_warning(self):
        return are_featured_submissions_visible(AnonymousUser(), self.request.event)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        schedule = ctx.get('schedule')
        version = self.version or (schedule.version if schedule else None)
        ctx['schedule_meta_json'] = build_featured_schedule_meta_json(self.request.event, schedule)
        ctx['schedule_page_version'] = version or ''
        return ctx
