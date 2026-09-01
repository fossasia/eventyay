from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import redirect
from django.template.defaultfilters import timeuntil
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from django.views.generic import TemplateView
from django_context_decorator import context
from django_scopes import scopes_disabled
from django.contrib import messages

from django.http import Http404

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

from eventyay.base.models import Submission, SubmissionStates, User
from eventyay.base.models.event import Event
from eventyay.base.models.log import LogEntry
from eventyay.base.models.organizer import Organizer
from eventyay.base.models.profile import SpeakerProfile
from eventyay.base.models.review import Review
from eventyay.base.settings import is_event_series_creation_enabled, is_meetup_creation_enabled
from eventyay.common.text.phrases import phrases
from eventyay.common.permissions import is_admin_mode_active
from eventyay.common.views.mixins import EventPermissionRequired, PermissionRequired
from eventyay.event.stages import get_stages
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

    def get_cfp_tiles(self, _now, can_change_submissions=False):
        result = []
        if not hasattr(self.request.event, 'cfp'):
            return result
        if self.request.event.cfp.is_open and (
            self.request.event.talks_published
            or self.request.event.private_testmode_talks_enabled
        ):
            result.append(
                {
                    'url': self.request.event.cfp.urls.public,
                    'large': phrases.cfp.go_to_cfp,
                    'priority': 20,
                }
            )
        max_deadline = self.request.event.cfp.max_deadline
        if max_deadline and _now < max_deadline:
            result.append(
                {
                    'large': timeuntil(max_deadline),
                    'small': _('until the CfP ends'),
                    'priority': 40,
                }
            )
            draft_proposals = Submission.all_objects.filter(
                state=SubmissionStates.DRAFT, event=self.request.event
            ).count()
            if draft_proposals and can_change_submissions:
                result.append(
                    {
                        'large': draft_proposals,
                        'small': ngettext_lazy(
                            'unsubmitted proposal draft',
                            'unsubmitted proposal drafts',
                            draft_proposals,
                        ),
                        'priority': 50,
                        'url': self.request.event.orga_urls.send_drafts_reminder,
                        'left': {
                            'text': _('Send reminder'),
                            'url': self.request.event.orga_urls.send_drafts_reminder,
                            'color': 'info',
                        },
                    }
                )
        return result

    def get_review_tiles(self, can_change_settings):
        result = []
        review_count = self.request.event.reviews.count()
        if review_count:
            active_reviewers = (
                self.request.event.reviewers.filter(reviews__isnull=False).order_by('id').distinct().count()
            )
            result.append({'large': review_count, 'small': _('Reviews'), 'priority': 60})
            result.append(
                {
                    'large': active_reviewers,
                    'small': _('Active reviewers'),
                    'url': (self.request.event.organizer.orga_urls.teams if can_change_settings else None),
                    'priority': 60,
                }
            )
        is_reviewer = self.request.event.teams.filter(members__in=[self.request.user], is_reviewer=True).exists()
        if is_reviewer:
            reviews_missing = get_missing_reviews(self.request.event, self.request.user).count()
            if reviews_missing:
                result.append(
                    {
                        'large': reviews_missing,
                        'small': ngettext_lazy(
                            'proposal is waiting for your review.',
                            'proposals are waiting for your review.',
                            reviews_missing,
                        ),
                        'url': self.request.event.orga_urls.reviews,
                        'priority': 21,
                    }
                )
        return result

    @context
    def history(self):
        return LogEntry.objects.filter(event=self.request.event).select_related('user', 'event')[:20]

    # ------------------------------------------------------------------
    # Talks dashboard helpers (control-center layout)
    # ------------------------------------------------------------------

    def _get_submission_counts(self, event):
        """Return a dict of submission counts by state."""
        counts = {
            'submitted': event.submissions.filter(state=SubmissionStates.SUBMITTED).count(),
            'accepted': event.submissions.filter(state=SubmissionStates.ACCEPTED).count(),
            'confirmed': event.submissions.filter(state=SubmissionStates.CONFIRMED).count(),
            'rejected': Submission.all_objects.filter(
                event=event, state=SubmissionStates.REJECTED
            ).count(),
            'withdrawn': Submission.all_objects.filter(
                event=event, state=SubmissionStates.WITHDRAWN
            ).count(),
            'canceled': Submission.all_objects.filter(
                event=event, state=SubmissionStates.CANCELED
            ).count(),
            'drafts': Submission.all_objects.filter(
                event=event, state=SubmissionStates.DRAFT
            ).count(),
            'total': Submission.all_objects.exclude(
                state__in=[SubmissionStates.DELETED, SubmissionStates.DRAFT]
            ).filter(event=event).count(),
        }
        counts['accepted_total'] = counts['accepted'] + counts['confirmed']
        return counts

    def _reviews_missing_for_user(self, event):
        if not (self.request.user and self.request.user.is_authenticated):
            return 0
        is_reviewer = event.teams.filter(members__in=[self.request.user], is_reviewer=True).exists()
        if not is_reviewer:
            return 0
        return get_missing_reviews(event, self.request.user).count()

    def _incomplete_speaker_qs(self, event):
        return SpeakerProfile.objects.filter(
            event=event,
            user__submissions__event=event,
            user__submissions__state__in=SubmissionStates.accepted_states,
        ).filter(
            Q(biography__isnull=True)
            | Q(biography='')
            | Q(user__avatar='')
            | Q(user__avatar__isnull=True)
        ).distinct()

    def _build_action_items(self, event, sub_counts, can_change_submissions, session_readiness):
        """Always return the four attention cards; mark inactive when clear."""
        items = []

        unconfirmed = sub_counts['accepted']
        items.append({
            'title': _('Unconfirmed sessions'),
            'desc': (
                ngettext_lazy(
                    'accepted session is waiting for speaker confirmation.',
                    'accepted sessions are waiting for speaker confirmation.',
                    max(unconfirmed, 1),
                )
                if unconfirmed
                else _('All accepted sessions have been confirmed.')
            ),
            'count': unconfirmed,
            'url': event.orga_urls.submissions + f'?state={SubmissionStates.ACCEPTED}',
            'btn': _('Review sessions'),
            'color': 'danger',
            'icon': 'exclamation-triangle',
            'active': bool(unconfirmed and can_change_submissions),
        })

        unscheduled = session_readiness['unscheduled']
        items.append({
            'title': _('Unscheduled sessions'),
            'desc': (
                ngettext_lazy(
                    'confirmed session is not assigned to any slot.',
                    'confirmed sessions are not assigned to any slot.',
                    max(unscheduled, 1),
                )
                if unscheduled
                else _('All confirmed sessions are scheduled.')
            ),
            'count': unscheduled,
            'url': event.orga_urls.schedule,
            'btn': _('Open schedule'),
            'color': 'warning',
            'icon': 'calendar-times-o',
            'active': bool(unscheduled and can_change_submissions),
        })

        speakers_incomplete = self._incomplete_speaker_qs(event).count()
        items.append({
            'title': _('Speakers incomplete'),
            'desc': (
                ngettext_lazy(
                    'speaker is missing bio, photo or profile details.',
                    'speakers are missing bio, photo or profile details.',
                    max(speakers_incomplete, 1),
                )
                if speakers_incomplete
                else _('All speaker profiles are complete.')
            ),
            'count': speakers_incomplete,
            'url': event.orga_urls.speakers + '?role=true',
            'btn': _('Review speakers'),
            'color': 'caution',
            'icon': 'user-times',
            'active': bool(speakers_incomplete and can_change_submissions),
        })

        pending_notifications = event.queued_mails.filter(sent__isnull=True).count()
        items.append({
            'title': _('Notifications pending'),
            'desc': (
                ngettext_lazy(
                    'email is waiting to be sent.',
                    'emails are waiting to be sent.',
                    max(pending_notifications, 1),
                )
                if pending_notifications
                else _('No pending email notifications.')
            ),
            'count': pending_notifications,
            'url': event.orga_urls.outbox,
            'btn': _('Send notifications'),
            'color': 'info',
            'icon': 'envelope',
            'active': bool(pending_notifications),
        })

        return items

    def _build_kpi_cards(self, event, sub_counts):
        """Primary + secondary metric cards for At a glance."""
        accepted_total = sub_counts['accepted_total']
        confirmed = sub_counts['confirmed']
        rejected = sub_counts['rejected']
        withdrawn = sub_counts['withdrawn']
        drafts = sub_counts.get('drafts', 0)
        total = sub_counts['total'] or 1
        speaker_count = self._accepted_speakers_qs(event).count()
        emails_sent = event.queued_mails.filter(sent__isnull=False).count()
        talk_count = event.talks.count()
        reviews_missing = self._reviews_missing_for_user(event)

        current_schedule = getattr(event, 'current_schedule', None)
        schedule_version = current_schedule.version if current_schedule else '—'

        active_reviewers = Review.objects.filter(submission__event=event).values('user').distinct().count()

        conversion = round(accepted_total / total * 100, 1) if sub_counts['total'] else None
        talk_status = event.talk_component_presale_status

        primary = [
            {
                'label': _('Submitted proposals'),
                'value': sub_counts['total'],
                'url': event.orga_urls.submissions,
                'link': _('View all'),
                'color': 'info',
                'icon': 'inbox',
                'hint': None,
                'tier': 'primary',
                'sparkline': 'blue',
            },
            {
                'label': _('Accepted proposals'),
                'value': accepted_total,
                'url': (
                    event.orga_urls.submissions
                    + f'?state={SubmissionStates.ACCEPTED}&state={SubmissionStates.CONFIRMED}'
                ),
                'link': _('View all'),
                'color': 'success',
                'icon': 'check',
                'hint': _('{rate}% conversion').format(rate=conversion) if conversion is not None else None,
                'tier': 'primary',
                'sparkline': 'green',
            },
            {
                'label': _('Confirmed sessions'),
                'value': confirmed,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.CONFIRMED}',
                'link': _('View all'),
                'color': 'success',
                'icon': 'check-circle',
                'hint': None,
                'tier': 'primary',
                'sparkline': 'green',
            },
            {
                'label': _('Scheduled sessions'),
                'value': talk_count,
                'url': event.orga_urls.schedule,
                'link': _('View schedule'),
                'color': 'success' if talk_count else 'muted',
                'icon': 'calendar',
                'hint': None,
                'tier': 'primary',
                'sparkline': 'blue',
            },
            {
                'label': _('Speakers'),
                'value': speaker_count,
                'url': event.orga_urls.speakers + '?role=true',
                'link': _('View speakers'),
                'color': 'info',
                'icon': 'users',
                'hint': None,
                'tier': 'primary',
                'sparkline': None,
            },
            {
                'label': _('Pending reviews'),
                'value': reviews_missing,
                'url': event.orga_urls.reviews,
                'link': _('Review now'),
                'color': 'warning' if reviews_missing else 'muted',
                'icon': 'clock-o',
                'hint': None,
                'tier': 'primary',
                'sparkline': None,
            },
        ]
        secondary = [
            {
                'label': _('Rejected proposals'),
                'value': rejected,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.REJECTED}',
                'link': _('View all'),
                'color': 'danger' if rejected else 'muted',
                'icon': 'times',
                'hint': None,
                'tier': 'secondary',
            },
            {
                'label': _('Withdrawn proposals'),
                'value': withdrawn,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.WITHDRAWN}',
                'link': _('View all'),
                'color': 'muted',
                'icon': 'undo',
                'hint': None,
                'tier': 'secondary',
            },
            {
                'label': _('Emails sent'),
                'value': emails_sent,
                'url': event.orga_urls.sent_mails,
                'link': _('View history'),
                'color': 'info',
                'icon': 'envelope',
                'hint': None,
                'tier': 'secondary',
            },
            {
                'label': _('Current schedule'),
                'value': schedule_version,
                'url': event.orga_urls.schedule,
                'link': _('View schedule'),
                'color': 'purple',
                'icon': 'calendar-check-o',
                'hint': None,
                'tier': 'secondary',
            },
            {
                'label': _('Active reviewers'),
                'value': active_reviewers,
                'url': event.orga_urls.reviews,
                'link': _('View reviews'),
                'color': 'muted',
                'icon': 'user-circle',
                'hint': None,
                'tier': 'secondary',
            },
            {
                'label': _('Unsubmitted drafts'),
                'value': drafts,
                'url': event.orga_urls.submissions + f'?state={SubmissionStates.DRAFT}',
                'link': _('View drafts'),
                'color': 'muted',
                'icon': 'pencil',
                'hint': None,
                'tier': 'secondary',
            },
        ]
        return {
            'primary': primary,
            'secondary': secondary,
            'all': primary + secondary,
            'talk_status': {
                'label': _('Talk component'),
                'text': talk_status['text'],
                'is_live': talk_status['is_live'],
                'css': talk_status['class'],
                'url': event.orga_urls.live,
                'link': _('Click to change'),
            },
        }

    def _build_funnel_data(self, sub_counts):
        """Return funnel rows with center-aligned bar widths.

        Width is proportional to each stage count (relative to the max),
        with a small floor so zero-count stages still show a thin bar.
        """
        total = sub_counts['total'] or 1
        accepted_total = sub_counts['accepted_total']

        rows = [
            {
                'label': _('Submitted'),
                'count': sub_counts['total'],
                'key': 'submitted',
            },
            {
                'label': _('Accepted'),
                'count': accepted_total,
                'key': 'accepted',
            },
            {
                'label': _('Confirmed'),
                'count': sub_counts['confirmed'],
                'key': 'confirmed',
            },
            {
                'label': _('Rejected'),
                'count': sub_counts['rejected'],
                'key': 'rejected',
            },
            {
                'label': _('Withdrawn'),
                'count': sub_counts['withdrawn'],
                'key': 'withdrawn',
            },
        ]

        max_count = max((row['count'] for row in rows), default=0) or 1
        for row in rows:
            row['width'] = max(14, round(row['count'] / max_count * 100, 1))

        conversion = round(accepted_total / total * 100, 1) if sub_counts['total'] else 0
        return {'rows': rows, 'conversion': conversion}

    def _slot_schedule(self, event):
        return getattr(event, 'wip_schedule', None) or getattr(event, 'current_schedule', None)

    def _build_session_readiness(self, event, sub_counts):
        """Return session readiness metrics for the readiness card."""
        confirmed = sub_counts['confirmed']
        unconfirmed = sub_counts['accepted']
        scheduled = event.talks.count()
        unscheduled = max(0, confirmed - scheduled)
        canceled = sub_counts.get('canceled', 0)

        missing_room_or_time = 0
        conflicts = 0
        schedule = self._slot_schedule(event)
        if schedule is not None:
            slots = schedule.talks.filter(submission__isnull=False).select_related('submission', 'room')
            confirmed_ids = set(
                event.submissions.filter(state=SubmissionStates.CONFIRMED).values_list('pk', flat=True)
            )
            slotted_ids = set()
            for slot in slots:
                if slot.submission_id not in confirmed_ids:
                    continue
                slotted_ids.add(slot.submission_id)
                if not slot.room_id or not slot.start:
                    missing_room_or_time += 1
            # Confirmed sessions with no slot at all count as missing room/time
            missing_room_or_time += max(0, len(confirmed_ids - slotted_ids))
        if schedule is not None and scheduled <= 250:
            warnings = schedule.get_all_talk_warnings()
            conflicts = sum(
                1
                for warns in warnings.values()
                for warn in warns
                if warn.get('type') in ('room_overlap', 'speaker', 'room')
            )

        scheduled_pct = round((scheduled / confirmed) * 100) if confirmed else 0
        return {
            'total': confirmed + unconfirmed,
            'confirmed': confirmed,
            'unconfirmed': unconfirmed,
            'scheduled': scheduled,
            'unscheduled': unscheduled,
            'missing_room_or_time': missing_room_or_time,
            'conflicts': conflicts,
            'canceled': canceled,
            'scheduled_pct': scheduled_pct,
            'sessions_url': event.orga_urls.submissions + f'?state={SubmissionStates.CONFIRMED}',
            'unconfirmed_url': event.orga_urls.submissions + f'?state={SubmissionStates.ACCEPTED}',
            'schedule_url': event.orga_urls.schedule,
        }

    def _accepted_speakers_qs(self, event):
        return User.objects.filter(
            submissions__event=event,
            submissions__state__in=SubmissionStates.accepted_states,
        ).distinct()

    def _build_speaker_readiness(self, event):
        """Return speaker readiness metrics for the readiness card."""
        accepted_speakers = self._accepted_speakers_qs(event)
        total_speakers = accepted_speakers.count()
        confirmed_speakers = accepted_speakers.filter(
            submissions__state=SubmissionStates.CONFIRMED,
            submissions__event=event,
        ).distinct().count()
        speaker_profiles = SpeakerProfile.objects.filter(
            event=event,
            user__submissions__event=event,
            user__submissions__state__in=SubmissionStates.accepted_states,
        ).distinct()
        missing_bio = speaker_profiles.filter(Q(biography__isnull=True) | Q(biography='')).count()
        missing_avatar = speaker_profiles.filter(
            Q(user__avatar='') | Q(user__avatar__isnull=True)
        ).count()
        speakers_without_session = (
            SpeakerProfile.objects.filter(event=event)
            .exclude(
                user__submissions__event=event,
                user__submissions__state__in=SubmissionStates.accepted_states,
            )
            .count()
        )
        incomplete = self._incomplete_speaker_qs(event).count()
        ready = max(0, total_speakers - incomplete)
        incomplete = max(0, total_speakers - ready)
        ready_pct = round((ready / total_speakers) * 100) if total_speakers else 100
        return {
            'total': total_speakers,
            'confirmed': confirmed_speakers,
            'missing_bio': missing_bio,
            'missing_avatar': missing_avatar,
            'speakers_without_session': speakers_without_session,
            'ready': ready,
            'incomplete': incomplete,
            'ready_pct': ready_pct,
            'speakers_url': event.orga_urls.speakers + '?role=true',
        }

    def _build_room_status(self, event, session_readiness):
        """Room assignment breakdown for analytics."""
        total = session_readiness['confirmed'] or 0
        schedule = self._slot_schedule(event)
        assigned = 0
        not_published = 0
        if schedule is not None:
            assigned = (
                schedule.talks.filter(
                    submission__isnull=False,
                    submission__state=SubmissionStates.CONFIRMED,
                    room__isnull=False,
                    room__deleted=False,
                )
                .values('submission_id')
                .distinct()
                .count()
            )
            not_published = (
                schedule.talks.filter(
                    submission__isnull=False,
                    submission__state=SubmissionStates.CONFIRMED,
                    room__isnull=False,
                    is_visible=False,
                )
                .values('submission_id')
                .distinct()
                .count()
            )
        not_assigned = max(0, total - assigned)
        def pct(n):
            return round((n / total) * 100, 1) if total else 0

        rows = [
            {
                'label': _('Assigned to room'),
                'count': assigned,
                'pct': pct(assigned),
                'status': 'success',
            },
            {
                'label': _('Room not assigned'),
                'count': not_assigned,
                'pct': pct(not_assigned),
                'status': 'warning' if not_assigned else 'success',
            },
            {
                'label': _('Room not published'),
                'count': not_published,
                'pct': pct(not_published),
                'status': 'warning' if not_published else 'success',
            },
        ]
        return {
            'rows': rows,
            'total': total,
            'schedule_url': event.orga_urls.schedule,
        }

    def _build_upcoming_items(self, event):
        """Upcoming deadlines and milestones for the Upcoming card."""
        items = []
        tz = event.tz
        _now = now()

        if hasattr(event, 'cfp') and event.cfp.deadline and event.cfp.deadline > _now:
            items.append({
                'when': event.cfp.deadline.astimezone(tz),
                'label': _('CfP deadline'),
                'group': 'soon',
            })
        for submission_type in event.submission_types.filter(deadline__isnull=False):
            if submission_type.deadline and submission_type.deadline > _now:
                items.append({
                    'when': submission_type.deadline.astimezone(tz),
                    'label': _('Deadline') + f' ({submission_type.name})',
                    'group': 'soon',
                })
        if event.date_from and event.date_from > _now:
            items.append({
                'when': event.date_from.astimezone(tz),
                'label': _('Event starts'),
                'group': 'event',
            })
        if event.date_to and event.date_to > _now and event.date_to != event.date_from:
            items.append({
                'when': event.date_to.astimezone(tz),
                'label': _('Event ends'),
                'group': 'event',
            })

        items.sort(key=lambda item: item['when'])
        today = _now.astimezone(tz).date()
        tomorrow = today + timedelta(days=1)
        for item in items:
            day = item['when'].date()
            if day == today:
                item['day_label'] = _('Today')
            elif day == tomorrow:
                item['day_label'] = _('Tomorrow')
            else:
                item['day_label'] = f"{item['when']:%b %d}"
            item['time_label'] = f"{item['when']:%H:%M}"
        return items[:6]

    def _build_quick_actions(self, event):
        return [
            {
                'label': _('Review proposals'),
                'url': event.orga_urls.reviews,
                'icon': 'eye',
            },
            {
                'label': _('Manage speakers'),
                'url': event.orga_urls.speakers + '?role=true',
                'icon': 'users',
            },
            {
                'label': _('Open schedule'),
                'url': event.orga_urls.schedule,
                'icon': 'calendar',
            },
            {
                'label': _('Send message'),
                'url': event.orga_urls.compose_mails,
                'icon': 'envelope',
            },
            {
                'label': _('Add session'),
                'url': event.orga_urls.new_submission,
                'icon': 'plus',
            },
        ]

    def _build_event_status(self, event, timeline):
        """Compact status badge derived from the live workflow stage."""
        talk_status = event.talk_component_presale_status
        current = next((step for step in timeline if step.get('phase') == 'current'), None)
        if talk_status['is_live'] and current and current.get('name'):
            # Prefer component live wording when talks are public
            if event.talks_published:
                return {
                    'text': _('Live'),
                    'tone': 'live',
                }
        if current:
            return {
                'text': current['name'],
                'tone': 'current',
            }
        if event.date_to and now() > event.date_to:
            return {'text': _('Wrapup'), 'tone': 'muted'}
        return {'text': talk_status['text'], 'tone': 'info'}

    def _enrich_timeline(self, timeline, event, sub_counts, session_readiness):
        """Add supporting status lines under each workflow step."""
        phase_labels = {
            'done': _('Completed'),
            'current': _('In progress'),
            'todo': _('Pending'),
        }
        enriched = []
        for step in timeline:
            detail = None
            name = str(step.get('name', ''))
            if 'CfP' in name or 'Call' in name:
                if hasattr(event, 'cfp') and event.cfp.deadline:
                    detail = f"{event.cfp.deadline.astimezone(event.tz):%b %d}"
                elif hasattr(event, 'cfp') and event.cfp.is_open:
                    detail = _('Open')
            elif 'Review' in name:
                if sub_counts['rejected']:
                    detail = _('{n} rejected').format(n=sub_counts['rejected'])
            elif 'Schedule' in name or 'schedule' in name.lower():
                if session_readiness['unscheduled']:
                    detail = _('{n} unscheduled').format(n=session_readiness['unscheduled'])
                elif session_readiness['scheduled']:
                    detail = _('{n} scheduled').format(n=session_readiness['scheduled'])
            elif step.get('phase') == 'current' and sub_counts['accepted']:
                detail = _('{n} unconfirmed').format(n=sub_counts['accepted'])

            enriched.append({
                **step,
                'status_label': phase_labels.get(step.get('phase'), ''),
                'detail': detail,
            })
        return enriched

    def _activity_type_meta(self, action_type):
        action = action_type or ''
        if 'mail' in action:
            return {'label': _('Email'), 'badge': 'email', 'icon': 'envelope'}
        if 'schedule' in action:
            return {'label': _('Schedule'), 'badge': 'scheduled', 'icon': 'calendar'}
        if 'review' in action:
            return {'label': _('Review'), 'badge': 'proposal', 'icon': 'eye'}
        if 'speaker' in action or 'user.profile' in action:
            return {'label': _('Speaker'), 'badge': 'proposal', 'icon': 'user'}
        if 'cfp' in action:
            return {'label': _('CfP'), 'badge': 'proposal', 'icon': 'bullhorn'}
        if 'reject' in action:
            return {'label': _('Rejected'), 'badge': 'rejected', 'icon': 'times'}
        if 'accept' in action or 'confirm' in action:
            return {'label': _('Accepted'), 'badge': 'accepted', 'icon': 'check'}
        return {'label': _('Session'), 'badge': 'proposal', 'icon': 'file-text-o'}

    def _build_recent_activity(self, event):
        """Return the 5 most recent talk-related log entries with display fields."""
        talk_action_prefixes = (
            'eventyay.submission.',
            'eventyay.speaker.',
            'eventyay.schedule.',
            'eventyay.mail.',
            'eventyay.cfp.',
            'eventyay.review.',
            'eventyay.user.profile.',
        )
        q = Q()
        for prefix in talk_action_prefixes:
            q |= Q(action_type__startswith=prefix)
        entries = (
            LogEntry.objects.filter(event=event)
            .filter(q)
            .select_related('user', 'event', 'content_type')
            .order_by('-datetime')[:8]
        )
        rows = []
        for entry in entries:
            meta = self._activity_type_meta(entry.action_type)
            reference = ''
            reference_url = ''
            obj = entry.content_object
            if obj is not None:
                reference = str(getattr(obj, 'title', None) or getattr(obj, 'name', None) or obj)
                orga_urls = getattr(obj, 'orga_urls', None)
                if orga_urls is not None:
                    try:
                        reference_url = orga_urls.base
                    except (AttributeError, ValueError, KeyError):
                        reference_url = ''
            try:
                message = entry.display()
            except (TypeError, AttributeError, ValueError):
                message = entry.action_type
            rows.append({
                'datetime': entry.datetime,
                'user': entry.user,
                'type_label': meta['label'],
                'badge': meta['badge'],
                'icon': meta['icon'],
                'reference': reference,
                'reference_url': reference_url,
                'message': message,
                'action_type': entry.action_type,
            })
        return rows

    def get_context_data(self, **kwargs):
        # Tiles can have priorities
        # Priorities are meant to be between 0 and 100
        # 0 is the first tile, the go-live tile
        # 100+ is whatever can go to the very end
        # actions should be between 10 and 30, with 20 being the "go to cfp" action
        # general stats start at 50
        result = super().get_context_data(**kwargs)
        event = self.request.event
        stages = get_stages(event)
        result['timeline'] = stages.values()
        result['go_to_target'] = 'schedule' if stages['REVIEW']['phase'] == 'done' else 'cfp'
        _now = now()
        today = _now
        can_change_settings = self.request.user.has_perm('base.update_event', event)
        can_change_submissions = self.request.user.has_perm('base.orga_update_submission', event)
        result['tiles'] = self.get_cfp_tiles(_now, can_change_submissions=can_change_submissions)
        if today < event.date_from:
            days = (event.date_from - today).days
            result['tiles'].append(
                {
                    'large': days,
                    'small': ngettext_lazy('day until event start', 'days until event start', days),
                    'priority': 10,
                }
            )
        elif today > event.date_to:
            days = (today - event.date_from).days
            result['tiles'].append(
                {
                    'large': days,
                    'small': ngettext_lazy('day since event end', 'days since event end', days),
                    'priority': 80,
                }
            )
        elif event.date_to != event.date_from:
            day = (today - event.date_from).days + 1
            result['tiles'].append(
                {
                    'large': _('Day {number}').format(number=day),
                    'small': _('of {total_days} days').format(total_days=(event.date_to - event.date_from).days + 1),
                    'url': event.urls.schedule + f'#{today.isoformat()}',
                    'priority': 10,
                }
            )
        if event.current_schedule:
            result['tiles'].append(
                {
                    'large': event.current_schedule.version,
                    'small': _('current schedule'),
                    'url': event.urls.schedule,
                    'priority': 25,
                }
            )

        talk_count = event.talks.count()
        accepted_count = event.submissions.filter(state=SubmissionStates.ACCEPTED).count()
        submission_count = event.submissions.count()
        pending_state_submissions = event.submissions.filter(pending_state__isnull=False).count()
        if talk_count or accepted_count:
            confirmed_count = event.submissions.filter(state=SubmissionStates.CONFIRMED).count()
            result['tiles'].append(
                {
                    # Don't show 0 here for events that do not use the scheduling
                    # component, instead show accepted + confirmed
                    'large': talk_count or (accepted_count + confirmed_count),
                    'small': ngettext_lazy('session', 'sessions', talk_count),
                    'url': event.orga_urls.submissions
                    + f'?state={SubmissionStates.ACCEPTED}&state={SubmissionStates.CONFIRMED}',
                    'priority': 55,
                    'right': {
                        'text': str(_('unconfirmed')) + f': {accepted_count}',
                        'url': event.orga_urls.submissions + f'?state={SubmissionStates.ACCEPTED}',
                        'color': 'error' if accepted_count else 'info',
                    },
                    'left': {
                        'text': str(_('confirmed')) + f': {confirmed_count}',
                        'url': event.orga_urls.submissions,
                        'color': 'success',
                    },
                }
            )
        elif submission_count:
            count = event.submissions.count()
            result['tiles'].append(
                {
                    'large': count,
                    'small': ngettext_lazy('proposal', 'proposals', count),
                    'url': event.orga_urls.submissions,
                    'priority': 60,
                }
            )
        if pending_state_submissions and pending_state_submissions > 0:
            states = '&'.join(
                [
                    f'state=pending_state__{state}'
                    for state, __ in SubmissionStates.get_choices()
                    if state not in (SubmissionStates.DRAFT, SubmissionStates.DELETED)
                ]
            )
            result['tiles'].append(
                {
                    'large': pending_state_submissions,
                    'small': ngettext_lazy(
                        'submission with pending changes',
                        'submissions with pending changes',
                        pending_state_submissions,
                    ),
                    'url': event.orga_urls.submissions + f'?{states}',
                    'priority': 56,
                }
            )
        submitter_count = event.submitters.count()
        speaker_count = event.speakers.count()
        rejected_count = event.submitters.filter(submissions__state=SubmissionStates.REJECTED).distinct().count()
        if speaker_count:
            result['tiles'].append(
                {
                    'large': speaker_count,
                    'small': ngettext_lazy('speaker', 'speakers', speaker_count),
                    'url': event.orga_urls.speakers + '?role=true',
                    'priority': 56,
                    'right': {
                        'text': _('rejected') + f': {rejected_count}',
                        'url': event.orga_urls.speakers + '?role=false',
                        'color': 'error',
                    },
                    'left': {
                        'text': phrases.submission.submitted + f': {submitter_count}',
                        'url': event.orga_urls.speakers,
                        'color': 'success',
                    },
                }
            )
        else:
            result['tiles'].append(
                {
                    'large': submitter_count,
                    'small': ngettext_lazy('submitter', 'submitters', submitter_count),
                    'url': event.orga_urls.speakers,
                    'priority': 60,
                }
            )
        count = event.queued_mails.filter(sent__isnull=False).count()
        result['tiles'].append(
            {
                'large': count,
                'small': ngettext_lazy('sent email', 'sent emails', count),
                'url': event.orga_urls.sent_mails,
                'priority': 80,
            }
        )
        result['tiles'] += self.get_review_tiles(can_change_settings=can_change_settings)
        result['tiles'].sort(key=lambda tile: tile.get('priority') or 100)

        # ------------------------------------------------------------------
        # Control-center dashboard context
        # ------------------------------------------------------------------
        sub_counts = self._get_submission_counts(event)
        session_readiness = self._build_session_readiness(event, sub_counts)
        timeline_steps = list(stages.values())
        result['timeline'] = self._enrich_timeline(timeline_steps, event, sub_counts, session_readiness)
        result['event_status'] = self._build_event_status(event, result['timeline'])
        result['action_items'] = self._build_action_items(
            event, sub_counts, can_change_submissions, session_readiness
        )
        result['kpi_cards'] = self._build_kpi_cards(event, sub_counts)
        result['funnel_data'] = self._build_funnel_data(sub_counts)
        result['session_readiness'] = session_readiness
        result['speaker_readiness'] = self._build_speaker_readiness(event)
        result['room_status'] = self._build_room_status(event, session_readiness)
        result['upcoming_items'] = self._build_upcoming_items(event)
        result['quick_actions'] = self._build_quick_actions(event)
        result['recent_activity'] = self._build_recent_activity(event)
        result['can_change_settings'] = can_change_settings
        result['can_change_submissions'] = can_change_submissions
        result['event_comment'] = getattr(event, 'comment', '') or ''
        result['event_date_range'] = event.get_date_range_display()

        return result

    def post(self, request, *args, **kwargs):
        """Handle internal note save from the talks dashboard."""
        if 'save_internal_note' not in request.POST and 'internal_note' not in request.POST:
            return redirect(request.event.orga_urls.base)
        if not request.user.has_perm('base.update_event', request.event):
            messages.error(request, _('You do not have permission to change event settings.'))
        else:
            # Prefer the textarea value; ignore a colliding submit-button value if present.
            note_values = request.POST.getlist('internal_note')
            note = (note_values[0] if note_values else '')[:1000]
            request.event.comment = note
            request.event.save(update_fields=['comment'])
            request.event.log_action('eventyay.event.comment', person=request.user, orga=True)
            messages.success(request, _('Internal note saved.'))
        return redirect(request.event.orga_urls.base)
