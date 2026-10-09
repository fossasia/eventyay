import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Min, Q, Value
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, ListView, TemplateView, View
from django_context_decorator import context
from django_scopes import scope, scopes_disabled

from eventyay.common.exceptions import SendMailException
from eventyay.common.text.phrases import phrases
from eventyay.common.views import CreateOrUpdateView
from eventyay.common.views.generic import OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    EventPermissionRequired,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from eventyay.event.forms import OrganizerForm
from eventyay.base.models import Event, Order, OrderPosition, User
from eventyay.base.models.organizer import Organizer
from eventyay.orga.forms.submission import get_speaker_choice_label
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
        return HttpResponseRedirect(reverse('eventyay_common:dashboard'))


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


SPEAKER_AUTOCOMPLETE_MIN_LENGTH = 3
SPEAKER_AUTOCOMPLETE_LIMIT = 8
SPEAKER_AUTOCOMPLETE_CANDIDATE_LIMIT = SPEAKER_AUTOCOMPLETE_LIMIT * 2


def speaker_autocomplete_results(*, event: Event, search: str) -> list[dict[str, str]]:
    """Return event-scoped speaker autocomplete matches.

    Sources are limited to the current event: speaker profiles, proposal
    speakers/authors/submitters, and registered attendees. Results are
    deduplicated by email.
    """
    query = (search or '').strip()
    if len(query) < SPEAKER_AUTOCOMPLETE_MIN_LENGTH:
        return []

    results: dict[str, dict[str, str]] = {}

    def add_result(*, email: str | None, name: str | None) -> None:
        if not email:
            return
        key = email.lower()
        existing = results.get(key)
        display_name = name or ''
        if existing:
            if display_name and not existing['name']:
                existing['name'] = display_name
                existing['label'] = get_speaker_choice_label(name=display_name, email=existing['email'])
            return
        results[key] = {
            'email': email,
            'name': display_name,
            'label': get_speaker_choice_label(name=display_name or None, email=email),
        }

    with scope(event=event, organizer=event.organizer):
        name_or_email = Q(fullname__icontains=query) | Q(email__icontains=query)
        users = (
            User.objects.filter(
                name_or_email,
                Q(profiles__event=event) | Q(submissions__event=event),
            )
            .distinct()
            .order_by(Lower('fullname'), Lower('email'))
            [:SPEAKER_AUTOCOMPLETE_CANDIDATE_LIMIT]
        )
        for user in users:
            add_result(email=user.email, name=user.fullname)

        no_attendee_email = Q(attendee_email__isnull=True) | Q(attendee_email='')
        attendee_match = (
            Q(attendee_email__icontains=query)
            | Q(attendee_name_cached__icontains=query)
            | (Q(order__email__icontains=query) & no_attendee_email)
        )
        
        effective_email = Coalesce(NullIf('attendee_email', Value('')), 'order__email')
        
        attendee_data = (
            OrderPosition.objects.filter(
                attendee_match,
                order__event=event,
                order__status__in=(Order.STATUS_PAID, Order.STATUS_PENDING),
                product__admission=True,
            )
            .annotate(effective_email=effective_email)
            .values('effective_email')
            .annotate(name=Min('attendee_name_cached'))
            .order_by('effective_email')
            [:SPEAKER_AUTOCOMPLETE_CANDIDATE_LIMIT]
        )
        for data in attendee_data:
            add_result(
                email=data['effective_email'],
                name=data['name'],
            )

    ordered = sorted(
        results.values(),
        key=lambda item: ((item['name'] or item['email']).lower(), item['email'].lower()),
    )
    return ordered[:SPEAKER_AUTOCOMPLETE_LIMIT]


class OrganizerSpeakerSearch(PermissionRequired, View):
    """Deprecated organizer-wide user search. Always returns no results."""

    permission_required = 'base.view_organizer'

    def get_permission_object(self):
        return self.request.organizer

    def get(self, request, *args, **kwargs):
        return JsonResponse({'count': 0, 'results': []})


class EventSpeakerAutocomplete(EventPermissionRequired, View):
    permission_required = 'base.orga_update_submission'

    def has_permission(self):
        request = getattr(self, 'request', None)
        if request and hasattr(request, 'user') and hasattr(request.user, 'has_active_staff_session') and request.user.has_active_staff_session(request.session.session_key):
            return True
        return super(PermissionRequired, self).has_permission()

    def get(self, request, *args, **kwargs):
        search = request.GET.get('search') or request.GET.get('q') or ''
        results = speaker_autocomplete_results(event=request.event, search=search)
        return JsonResponse({'count': len(results), 'results': results})


