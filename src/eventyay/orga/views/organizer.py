import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView
from django_context_decorator import context
from django_scopes import scopes_disabled

from eventyay.common.exceptions import SendMailException
from eventyay.common.text.phrases import phrases
from eventyay.common.views import CreateOrUpdateView
from eventyay.common.views.generic import OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from eventyay.event.forms import OrganizerForm
from eventyay.base.models import Event, User
from eventyay.base.models.organizer import Organizer
from eventyay.person.forms import UserSpeakerFilterForm

logger = logging.getLogger(__name__)


class OrganizerDetail(PermissionRequired, CreateOrUpdateView):
    template_name = "orga/organizer/detail.html"
    model = Organizer
    permission_required = "base.update_organizer"
    form_class = OrganizerForm

    def get_object(self, queryset=None):
        return getattr(self.request, "organizer", None)

    @cached_property
    def object(self):
        return self.get_object()

    def get_permission_object(self):
        return self.object

    def form_valid(self, form):
        result = super().form_valid(form)
        if form.has_changed():
            messages.success(self.request, phrases.base.saved)
        return result

    def get_success_url(self):
        return self.request.path


class OrganizerDelete(PermissionRequired, ActionConfirmMixin, DetailView):
    permission_required = "base.administrator_user"
    model = Organizer
    action_text = (
        _(
            "ALL related data for ALL events, such as proposals, and speaker profiles, and uploads, "
            "will also be deleted and cannot be restored."
        )
        + " "
        + phrases.base.delete_warning
    )

    def get_object(self, queryset=None):
        return self.request.organizer

    def get_permission_object(self, queryset=None):
        return self.request.user

    def action_object_name(self):
        return _("Organizer") + f": {self.get_object().name}"

    @property
    def action_back_url(self):
        return self.get_object().orga_urls.settings

    def post(self, *args, **kwargs):
        organizer = self.get_object()
        organizer.shred(person=self.request.user)
        messages.success(
            self.request, _("The organizer and all related data have been deleted.")
        )
        return HttpResponseRedirect(reverse("orga:event.list"))


def get_speaker_access_events_for_user(*, user, organizer):
    events = set()
    no_access_events = set()
    # Use prefetch_related for efficiency if called often
    teams = user.teams.filter(organizer=organizer).prefetch_related(
        "limit_events", "limit_tracks"
    )
    for team in teams:
        if team.can_change_submissions:
            if team.all_events:
                # This user has access to all speakers for all events,
                # so we can cut our logic short here.
                return organizer.events.all()
            else:
                events.update(team.limit_events.values_list("pk", flat=True))
        elif team.is_reviewer and not team.limit_tracks.exists():
            # Reviewers *can* have access to speakers, but they do not necessarily
            # do, so we need to check permissions for each event. We do skip teams
            # that are limited to specific tracks.
            team_events = None
            if team.all_events:
                team_events = organizer.events.all()
            else:
                team_events = team.limit_events.all()
            if team_events:
                for event in team_events:
                    if event.pk in events or event.pk in no_access_events:
                        continue
                    if user.has_perm("base.orga_list_speakerprofile", event):
                        events.add(event.pk)
                    else:
                        no_access_events.add(event.pk)
    return Event.objects.filter(pk__in=list(events))


@method_decorator(scopes_disabled(), "dispatch")
class OrganizerSpeakerList(
    PermissionRequired, Sortable, Filterable, PaginationMixin, ListView
):
    template_name = "orga/organizer/speaker_list.html"
    permission_required = "base.view_organizer"
    context_object_name = "speakers"
    default_filters = ("email__icontains", "fullname__icontains")
    sortable_fields = ("email", "fullname", "accepted_submission_count", "submission_count")
    default_sort_field = "fullname"

    def get_permission_object(self):
        return self.request.organizer

    def get_filter_form(self):
        return UserSpeakerFilterForm(self.request.GET, events=self.events)

    @context
    @cached_property
    def events(self):
        return get_speaker_access_events_for_user(
            user=self.request.user, organizer=self.request.organizer
        )

    def get_queryset(self):
        qs = self.filter_queryset(User.objects.all())
        return self.sort_queryset(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[self.context_object_name] = list(context[self.context_object_name])
        return context


def speaker_search(request, *args, **kwargs):
    search = request.GET.get("search")
    if not search or len(search) < 3:
        return JsonResponse({"count": 0, "results": []})

    with scopes_disabled():
        events = get_speaker_access_events_for_user(
            user=request.user, organizer=request.organizer
        )
        users = (
            User.objects.filter(profiles__event__in=events)
            .filter(Q(fullname__icontains=search) | Q(email__icontains=search))
            .distinct()[:8]
        )
        users = list(users)

    return JsonResponse(
        {
            "count": len(users),
            "results": [{"email": user.email, "name": user.fullname} for user in users],
        }
    )


