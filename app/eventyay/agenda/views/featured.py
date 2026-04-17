from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.generic import TemplateView
from django_context_decorator import context

from eventyay.common.views import conditional_cache_page
from eventyay.common.permissions import is_admin_mode_active
from eventyay.common.views.mixins import EventPermissionRequired
from eventyay.base.models.submission import SubmissionStates
from eventyay.talk_rules.submission import (
    are_featured_submissions_visible,
    schedule_widget_featured_cache_key_part,
)


def sneakpeek_redirect(request, *args, **kwargs):
    return HttpResponsePermanentRedirect(request.event.urls.featured)


def is_cacheable_public_featured_request(request, organizer=None, event=None, **kwargs):
    """Cache only cookie-less anonymous requests on the featured page."""
    match = request.resolver_match
    if not match or match.url_name != 'featured':
        return False
    # Avoid parsing cookies for requests that should never be cached.
    if request.META.get('HTTP_COOKIE'):
        return False
    return request.user.is_anonymous


def public_featured_page_cache_prefix(request, organizer=None, event=None, **kwargs):
    featured_part = schedule_widget_featured_cache_key_part(request.event)
    return f'public-featured-v1-pub{int(request.event.talks_published)}-{featured_part}'


@method_decorator(
    conditional_cache_page(
        60,
        key_prefix=public_featured_page_cache_prefix,
        condition=is_cacheable_public_featured_request,
        server_timeout=5 * 60,
    ),
    name='dispatch',
)
class FeaturedView(EventPermissionRequired, TemplateView):
    template_name = 'agenda/featured.html'
    permission_required = 'base.list_featured_submission'

    def has_permission(self):
        """Gate on org "show featured" + schedule rules, not ``list_featured`` (orga always passes that)."""
        request = self.request
        if is_admin_mode_active(request):
            return True
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

    def dispatch(self, request, *args, **kwargs):
        can_see_featured = self.has_permission()
        can_schedule = request.user.has_perm('base.list_schedule', request.event)

        if not can_see_featured and can_schedule:
            return HttpResponseRedirect(request.event.urls.schedule)
        return super().dispatch(request, *args, **kwargs)
