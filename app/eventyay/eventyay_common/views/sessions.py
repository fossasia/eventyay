from logging import getLogger
from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models.functions import Lower
from django.shortcuts import redirect
from django.views.generic.list import ListView
from django_scopes import scopes_disabled

from eventyay.base.models import Submission, User

from ..forms.filters import SessionsFilterForm


logger = getLogger(__name__)


class MySessionsView(LoginRequiredMixin, ListView):
    template_name = 'eventyay_common/sessions/sessions.html'
    paginate_by = 20

    def get_queryset(self):
        user = cast(User, self.request.user)
        with scopes_disabled():
            qs = (
                Submission.objects.annotate(speaker_email=Lower('speakers__email'))
                .filter(speaker_email__in=user.email_addresses)
                .select_related('event', 'event__organizer', 'submission_type')
                .order_by('-event__date_from')
            )

        filter_form = SessionsFilterForm(self.request.GET, user=user)
        if filter_form.is_valid():
            event = filter_form.cleaned_data.get('event')
            search = filter_form.cleaned_data.get('search')

            if event:
                qs = qs.filter(event=event)

            if search:
                qs = qs.filter(title__icontains=search)

        return qs


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filter_form'] = SessionsFilterForm(self.request.GET, user=self.request.user)
        return ctx

    def get(self, request, *args, **kwargs):
        filter_form = SessionsFilterForm(self.request.GET, user=self.request.user)
        # If filter form is invalid, strip the 'event' from URL and redirect to this new URL.
        if not filter_form.is_valid():
            new_url_query = request.GET.copy()
            new_url_query.pop('event', None)
            new_url = request.path + '?' + new_url_query.urlencode()
            logger.info('To redirect to "%s" because the filter values are invalid.', new_url)
            return redirect(new_url)
        return super().get(request, *args, **kwargs)
