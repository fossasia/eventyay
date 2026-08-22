from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.views.generic import TemplateView, View
from django_context_decorator import context
from django_scopes import scopes_disabled

def legacy_orga_event_redirect(request, event):
    from eventyay.base.models import Event
    with scopes_disabled():
        events = Event.objects.filter(slug__iexact=event)
        if events.count() == 1:
            e = events.first()
            url = f"/orga/event/{e.organizer.slug}/{e.slug}/"
            if request.META.get('QUERY_STRING'):
                url += '?' + request.META['QUERY_STRING']
            return redirect(url, permanent=True)
        if events.count() > 1 and request.user.is_authenticated:
            user_events = events.filter(
                Q(organizer__id__in=request.user.teams.values_list('organizer_id', flat=True)) |
                Q(submissions__speakers__in=[request.user])
            ).distinct()
            if user_events.count() == 1:
                e = user_events.first()
                url = f"/orga/event/{e.organizer.slug}/{e.slug}/"
                if request.META.get('QUERY_STRING'):
                    url += '?' + request.META['QUERY_STRING']
                return redirect(url, permanent=True)
        raise Http404()

from eventyay.base.models import Submission, SubmissionStates
from eventyay.base.models.event import Event
from eventyay.base.models.log import ActivityLog, LogEntry
from eventyay.base.models.organizer import Organizer
from eventyay.base.settings import is_event_series_creation_enabled, is_meetup_creation_enabled
from eventyay.common.text.phrases import phrases
from eventyay.common.permissions import is_admin_mode_active
from eventyay.common.views.mixins import EventPermissionRequired, PermissionRequired
from eventyay.event.stages import get_stages, get_workflow_steps
from eventyay.orga.views.submission import SubmissionStatsMixin
from eventyay.talk_rules.submission import get_missing_reviews


def start_redirect_view(request):
    with scopes_disabled():
        orga_events = set(request.user.get_events_with_any_permission())
        speaker_events = set(Event.objects.filter(submissions__speakers__in=[request.user]))

    # Users with only one event, in only one role, are redirected to that event
    if len(orga_events | speaker_events) == 1 and not (orga_events and speaker_events):
        if orga_events:
            return redirect(orga_events.pop().orga_urls.base)
        return redirect(speaker_events.pop().urls.user_submissions)

    return redirect(reverse('eventyay_common:dashboard'))


class DashboardEventListView(TemplateView):
    template_name = 'orga/event_list.html'

    @property
    def base_queryset(self):
        return self.request.user.get_events_with_any_permission()

    @cached_property
    def queryset(self):
        if is_admin_mode_active(self.request):
            qs = Event.objects.all()
        else:
            qs = self.base_queryset.annotate(
                submission_count=Count(
                    'submissions',
                    filter=Q(
                        submissions__state__in=[
                            state
                            for state in SubmissionStates.display_values.keys()
                            if state not in (SubmissionStates.DELETED, SubmissionStates.DRAFT)
                        ]
                    ),
                )
            ).order_by('-date_from')
        if search := self.request.GET.get('q'):
            qs = qs.filter(Q(name__icontains=search) | Q(slug__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_orga_events'] = []
        context['past_orga_events'] = []
        for event in self.queryset:
            if event.date_to >= now():
                context['current_orga_events'].insert(0, event)
            else:
                context['past_orga_events'].append(event)
        context['speaker_events'] = (
            Event.objects.filter(submissions__speakers__in=[self.request.user]).distinct().order_by('-date_from')
        )
        context['event_series_creation_enabled'] = is_event_series_creation_enabled(self.request)
        context['meetup_creation_enabled'] = is_meetup_creation_enabled(self.request)
        return context


class DashboardOrganizerEventListView(PermissionRequired, DashboardEventListView):
    permission_required = 'base.view_organizer'

    def get_permission_object(self):
        return self.request.organizer

    @property
    def base_queryset(self):
        return self.request.organizer.events.all()

    @context
    def hide_speaker_events(self):
        return True


class DashboardOrganizerListView(PermissionRequired, TemplateView):
    template_name = 'orga/organizer/list.html'
    permission_required = 'base.list_organizer'

    def filter_organizer(self, organizer, query):
        name = {'en': organizer.name} if isinstance(organizer.name, str) else organizer.name.data
        name = {'en': name} if isinstance(name, str) else name
        return query in organizer.slug or any(query in value for value in name.values())

    @context
    def organizers(self):
        if self.request.user.is_administrator:
            orgs = Organizer.objects.all()
        else:
            orgs = Organizer.objects.filter(
                pk__in={
                    team.organizer_id for team in self.request.user.teams.filter(can_change_organizer_settings=True)
                }
            )
        orgs = orgs.annotate(
            event_count=Count('events', distinct=True),
            team_count=Count('teams', distinct=True),
        )
        query = self.request.GET.get('q')
        if not query:
            return orgs
        query = query.lower().strip()
        return [org for org in orgs if self.filter_organizer(org, query)]


class EventDashboardView(EventPermissionRequired, SubmissionStatsMixin, TemplateView):
    template_name = 'orga/event/dashboard.html'
    permission_required = 'base.talk_orga_access_event'

    @context
    def history(self):
        return ActivityLog.objects.filter(event=self.request.event).select_related('person', 'event')[:10]

    def _get_action_items(self, event):
        """Build action-required cards for items needing organiser attention."""
        items = []
        accepted_count = event.submissions.filter(state=SubmissionStates.ACCEPTED).count()
        confirmed_count = event.submissions.filter(state=SubmissionStates.CONFIRMED).count()
        talk_count = event.talks.count()
        unscheduled = confirmed_count - talk_count if confirmed_count > talk_count else 0

        if accepted_count:
            items.append({
                'title': _('Unconfirmed sessions'),
                'description': ngettext_lazy(
                    '%(count)d accepted session is waiting for speaker confirmation.',
                    '%(count)d accepted sessions are waiting for speaker confirmation.',
                    accepted_count,
                ) % {'count': accepted_count},
                'count': accepted_count,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.ACCEPTED}',
                'action_label': _('Review sessions'),
                'color': 'warning',
            })

        if unscheduled:
            items.append({
                'title': _('Unscheduled sessions'),
                'description': ngettext_lazy(
                    '%(count)d confirmed session is not assigned to any slot.',
                    '%(count)d confirmed sessions are not assigned to any slot.',
                    unscheduled,
                ) % {'count': unscheduled},
                'count': unscheduled,
                'url': event.orga_urls.schedule,
                'action_label': _('Open schedule'),
                'color': 'warning',
            })

        # Speakers with incomplete profiles (missing biography)
        from eventyay.base.models.profile import SpeakerProfile

        incomplete_speakers = SpeakerProfile.objects.filter(
            event=event,
            user__in=event.speakers,
            biography__isnull=True,
        ).count() + SpeakerProfile.objects.filter(
            event=event,
            user__in=event.speakers,
            biography='',
        ).count()
        if incomplete_speakers:
            items.append({
                'title': _('Speakers incomplete'),
                'description': ngettext_lazy(
                    '%(count)d speaker is missing a biography.',
                    '%(count)d speakers are missing a biography.',
                    incomplete_speakers,
                ) % {'count': incomplete_speakers},
                'count': incomplete_speakers,
                'url': event.orga_urls.speakers,
                'action_label': _('Review speakers'),
                'color': 'info',
            })

        # Pending reviews
        is_reviewer = event.teams.filter(
            members__in=[self.request.user], is_reviewer=True,
        ).exists()
        if is_reviewer:
            reviews_missing = get_missing_reviews(event, self.request.user).count()
            if reviews_missing:
                items.append({
                    'title': _('Pending reviews'),
                    'description': ngettext_lazy(
                        '%(count)d proposal is waiting for your review.',
                        '%(count)d proposals are waiting for your review.',
                        reviews_missing,
                    ) % {'count': reviews_missing},
                    'count': reviews_missing,
                    'url': event.orga_urls.reviews,
                    'action_label': _('Start reviewing'),
                    'color': 'warning',
                })

        return items

    def _get_kpi_cards(self, event):
        """Build KPI metric cards for the At a Glance section."""
        submission_count = event.submissions.count()
        accepted_count = event.submissions.filter(state=SubmissionStates.ACCEPTED).count()
        confirmed_count = event.submissions.filter(state=SubmissionStates.CONFIRMED).count()
        talk_count = event.talks.count()
        speaker_count = event.speakers.count()
        review_count = event.reviews.count()
        rejected_count = event.submissions.filter(state=SubmissionStates.REJECTED).count()
        withdrawn_count = event.submissions.filter(state=SubmissionStates.WITHDRAWN).count()
        emails_sent = event.queued_mails.filter(sent__isnull=False).count()

        return [
            {
                'label': _('Submitted proposals'),
                'value': submission_count,
                'url': event.orga_urls.submissions,
                'icon': 'inbox',
            },
            {
                'label': _('Accepted proposals'),
                'value': accepted_count,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.ACCEPTED}',
                'icon': 'check-circle',
            },
            {
                'label': _('Confirmed sessions'),
                'value': confirmed_count,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.CONFIRMED}',
                'icon': 'thumbs-up',
            },
            {
                'label': _('Scheduled sessions'),
                'value': talk_count,
                'url': event.urls.schedule if event.current_schedule else '',
                'icon': 'calendar',
            },
            {
                'label': _('Speakers'),
                'value': speaker_count,
                'url': event.orga_urls.speakers + '?role=true',
                'icon': 'users',
            },
            {
                'label': _('Pending reviews'),
                'value': review_count,
                'url': event.orga_urls.reviews,
                'icon': 'eye',
            },
            {
                'label': _('Rejected proposals'),
                'value': rejected_count,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.REJECTED}',
                'icon': 'times-circle',
            },
            {
                'label': _('Withdrawn proposals'),
                'value': withdrawn_count,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.WITHDRAWN}',
                'icon': 'undo',
            },
            {
                'label': _('Emails sent'),
                'value': emails_sent,
                'url': event.orga_urls.sent_mails,
                'icon': 'envelope',
            },
        ]

    def _get_session_readiness(self, event):
        """Build session readiness summary metrics."""
        confirmed = event.submissions.filter(state=SubmissionStates.CONFIRMED).count()
        talk_count = event.talks.count()
        unscheduled = confirmed - talk_count if confirmed > talk_count else 0
        canceled = event.submissions.filter(state=SubmissionStates.CANCELED).count()

        return [
            {
                'label': _('Confirmed sessions'),
                'value': confirmed,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.CONFIRMED}',
            },
            {
                'label': _('Scheduled sessions'),
                'value': talk_count,
                'url': event.urls.schedule if event.current_schedule else '',
            },
            {
                'label': _('Unscheduled sessions'),
                'value': unscheduled,
                'url': event.orga_urls.schedule if unscheduled else '',
                'color': 'warning' if unscheduled else '',
            },
            {
                'label': _('Canceled sessions'),
                'value': canceled,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.CANCELED}' if canceled else '',
                'color': 'danger' if canceled else '',
            },
        ]

    def _get_speaker_readiness(self, event):
        """Build speaker readiness summary metrics."""
        from eventyay.base.models.profile import SpeakerProfile

        speaker_users = event.speakers
        total = speaker_users.count()

        profiles = SpeakerProfile.objects.filter(event=event, user__in=speaker_users)
        missing_bio = profiles.filter(Q(biography__isnull=True) | Q(biography='')).count()
        missing_avatar = speaker_users.filter(
            Q(avatar='') | Q(avatar__isnull=True),
            Q(avatar_source='') | Q(avatar_source__isnull=True),
        ).count()

        # Speakers without any accepted/confirmed session
        speakers_without_session = speaker_users.exclude(
            submissions__event=event,
            submissions__state__in=SubmissionStates.accepted_states,
        ).count()

        return [
            {
                'label': _('Total speakers'),
                'value': total,
                'url': event.orga_urls.speakers + '?role=true',
            },
            {
                'label': _('Missing biography'),
                'value': missing_bio,
                'url': event.orga_urls.speakers,
                'color': 'warning' if missing_bio else '',
            },
            {
                'label': _('Missing profile image'),
                'value': missing_avatar,
                'url': event.orga_urls.speakers,
                'color': 'warning' if missing_avatar else '',
            },
            {
                'label': _('Speakers without session'),
                'value': speakers_without_session,
                'url': event.orga_urls.speakers + '?role=false',
                'color': 'info' if speakers_without_session else '',
            },
        ]

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        event = self.request.event

        # Workflow timeline (new 7-step model)
        result['workflow_steps'] = get_workflow_steps(event)

        # Legacy timeline for backward compat (kept but not rendered by default)
        stages = get_stages(event)
        result['timeline'] = stages.values()
        result['go_to_target'] = 'schedule' if stages['REVIEW']['phase'] == 'done' else 'cfp'

        can_change_settings = self.request.user.has_perm('base.change_settings.event', event)
        result['can_change_settings'] = can_change_settings

        # Action items
        result['action_items'] = self._get_action_items(event)

        # KPI cards (At a Glance)
        result['kpi_cards'] = self._get_kpi_cards(event)

        # Session readiness
        result['session_readiness'] = self._get_session_readiness(event)

        # Speaker readiness
        result['speaker_readiness'] = self._get_speaker_readiness(event)

        # Internal note
        result['internal_note'] = event.settings.get('dashboard_internal_note', default='')

        return result


class SaveInternalNoteView(EventPermissionRequired, View):
    """AJAX endpoint to save the dashboard internal note."""

    permission_required = 'base.talk_orga_access_event'

    def post(self, request, *args, **kwargs):
        note = request.POST.get('note', '')
        request.event.settings.set('dashboard_internal_note', note)
        return JsonResponse({'status': 'ok'})
