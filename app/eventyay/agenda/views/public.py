from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View
from django_context_decorator import context
from django_scopes import scope

from eventyay.agenda.views.speaker import ScheduleDataMixin
from eventyay.base.models import SubmissionFavourite, User


def _is_email_like(value: str) -> bool:
    value = (value or '').strip()
    if '@' not in value:
        return False
    local_part, _, domain = value.partition('@')
    if not local_part or not domain:
        return False
    return True


class PublicStarredScheduleView(ScheduleDataMixin, TemplateView):
    template_name = 'agenda/public_starred.html'

    @cached_property
    def public_user(self) -> User:
        user = (
            User.objects.filter(
                code__iexact=self.kwargs['code'],
                deleted=False,
                show_publicly=True,
            )
            .only('id', 'code', 'fullname', 'nick', 'avatar', 'show_publicly', 'deleted')
            .first()
        )
        if not user:
            raise Http404()
        return user

    def dispatch(self, request, *args, **kwargs):
        if not request.event.current_schedule:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    @context
    def profile_user(self) -> User:
        return self.public_user

    @context
    def public_favs_url(self) -> str:
        return reverse(
            'agenda:public-stars-json',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
                'code': self.public_user.code,
            },
        )

    @context
    def page_title(self) -> str:
        display_name = self.public_user.get_display_name()
        if _is_email_like(display_name):
            display_name = _('Anonymous (name not shared)')
        return _('%(name)s’s starred sessions') % {'name': display_name}


class PublicStarredScheduleDataView(View):

    @cached_property
    def public_user(self) -> User:
        user = (
            User.objects.filter(
                code__iexact=self.kwargs['code'],
                deleted=False,
                show_publicly=True,
            )
            .only('id', 'code', 'show_publicly', 'deleted')
            .first()
        )
        if not user:
            raise Http404()
        return user

    def get(self, request, event, code, **kwargs):
        schedule = request.event.current_schedule
        if not schedule:
            raise Http404()

        # Only include talks that are visible in the published schedule.
        visible_submission_ids = schedule.talks.filter(is_visible=True).values_list(
            'submission_id', flat=True
        )
        with scope(event=request.event):
            favs = list(
                SubmissionFavourite.objects.filter(
                    user=self.public_user,
                    submission__event=request.event,
                    submission_id__in=visible_submission_ids,
                )
                .values_list('submission__code', flat=True)
                .order_by('submission__code')
            )

        user = self.public_user
        display_name = user.get_display_name() or user.code
        if _is_email_like(display_name):
            display_name = None  # don't leak email
        return JsonResponse({'name': display_name, 'favs': favs})
