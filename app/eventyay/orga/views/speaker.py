import json
import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, FormView, ListView, View
from django_context_decorator import context

from eventyay.agenda.views.utils import get_schedule_exporters
from eventyay.common.exceptions import SendMailException
from eventyay.common.image import gravatar_csp
from eventyay.common.text.phrases import phrases
from eventyay.common.views.generic import CreateOrUpdateView, OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from eventyay.orga.forms.speaker import SpeakerExportForm
from eventyay.person.forms import (
    SpeakerFilterForm,
    SpeakerInformationForm,
    SpeakerProfileForm,
)
from eventyay.base.models import SpeakerProfile, User
from eventyay.base.models.information import SpeakerInformation
from eventyay.talk_rules.person import is_only_reviewer
from eventyay.submission.forms import TalkQuestionsForm
from eventyay.base.models import Answer
from eventyay.base.models.submission import SubmissionStates
from eventyay.talk_rules.submission import limit_for_reviewers, speaker_profiles_for_user

logger = logging.getLogger(__name__)


class SpeakerList(EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView):
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    default_filters = ('user__email__icontains', 'user__fullname__icontains')
    sortable_fields = ('user__email', 'user__fullname', 'featured_order')
    default_sort_field = 'featured_order'
    secondary_sort = {'featured_order': ['user__fullname']}
    permission_required = 'base.orga_list_speakerprofile'

    def get_filter_form(self):
        any_arrived = SpeakerProfile.objects.filter(event=self.request.event, has_arrived=True).exists()
        return SpeakerFilterForm(self.request.GET, event=self.request.event, filter_arrival=any_arrived)

    def get_queryset(self):
        # Show ALL speakers for the event, not just those with submissions
        # This allows organizers to feature and reorder any speaker (per issue #1709)
        qs = (
            SpeakerProfile.objects.filter(event=self.request.event)
            .select_related('event', 'user')
            .annotate(
                submission_count=Count(
                    'user__submissions',
                    filter=Q(user__submissions__event=self.request.event),
                    distinct=True,
                ),
                accepted_submission_count=Count(
                    'user__submissions',
                    filter=Q(user__submissions__event=self.request.event)
                    & Q(user__submissions__state__in=SubmissionStates.accepted_states),
                    distinct=True,
                ),
            )
        )

        qs = self.filter_queryset(qs)

        question = self.request.GET.get('question')
        unanswered = self.request.GET.get('unanswered')
        answer = self.request.GET.get('answer')
        option = self.request.GET.get('answer__options')
        if question and (answer or option):
            if option:
                answers = Answer.objects.filter(
                    person_id=OuterRef('user_id'),
                    question_id=question,
                    options__pk=option,
                )
            else:
                answers = Answer.objects.filter(
                    person_id=OuterRef('user_id'),
                    question_id=question,
                    answer__exact=answer,
                )
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=True)
        elif question and unanswered:
            answers = Answer.objects.filter(question_id=question, person_id=OuterRef('user_id'))
            qs = qs.annotate(has_answer=Exists(answers)).filter(has_answer=False)
        
        # Ensure deterministic ordering for PostgreSQL before applying distinct
        qs = qs.order_by('id').distinct()
        # Apply sorting: use sort_queryset() which respects ?sort= parameter or uses default_sort_field
        qs = self.sort_queryset(qs)
        return qs



class SpeakerViewMixin(PermissionRequired):
    def get_object(self):
        if self.request.user.has_perm('base.orga_list_speakerprofile', self.request.event):
            qs = User.objects.filter(profiles__event=self.request.event)
        else:
            qs = User.objects.filter(profiles__in=speaker_profiles_for_user(self.request.event, self.request.user))
        
        return get_object_or_404(
            qs.order_by('id').distinct(),
            code=self.kwargs['code'],
        )

    @cached_property
    def object(self):
        return self.get_object()

    @context
    @cached_property
    def profile(self):
        return self.object.event_profile(self.request.event)

    def get_permission_object(self):
        return self.profile

    @cached_property
    def permission_object(self):
        return self.get_permission_object()


@method_decorator(gravatar_csp(), name='dispatch')
class SpeakerDetail(SpeakerViewMixin, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/form.html'
    form_class = SpeakerProfileForm
    model = User
    permission_required = 'base.orga_list_speakerprofile'
    write_permission_required = 'base.update_speakerprofile'

    def get_success_url(self) -> str:
        return self.profile.orga_urls.base

    @context
    @cached_property
    def submissions(self, **kwargs):
        qs = self.request.event.submissions.filter(speakers__in=[self.object])
        if is_only_reviewer(self.request.user, self.request.event):
            return limit_for_reviewers(qs, self.request.event, self.request.user)
        return qs

    @context
    @cached_property
    def accepted_submissions(self, **kwargs):
        qs = self.submissions.filter(state__in=SubmissionStates.accepted_states)
        return qs

    @context
    @cached_property
    def mails(self):
        return self.object.mails.filter(sent__isnull=False, event=self.request.event).order_by('-sent')

    @context
    @cached_property
    def questions_form(self):
        speaker = self.get_object()
        return TalkQuestionsForm(
            self.request.POST if self.request.method == 'POST' else None,
            files=self.request.FILES if self.request.method == 'POST' else None,
            target='speaker',
            speaker=speaker,
            event=self.request.event,
            for_reviewers=(
                not self.request.user.has_perm('base.orga_update_submission', self.request.event)
                and self.request.user.has_perm('base.list_review', self.request.event)
            ),
        )

    @transaction.atomic()
    def form_valid(self, form):
        result = super().form_valid(form)
        if not self.questions_form.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        self.questions_form.save()
        if form.has_changed():
            form.instance.log_action('eventyay.user.profile.update', person=self.request.user, orga=True)
        if form.has_changed() or self.questions_form.has_changed():
            self.request.event.cache.set('rebuild_schedule_export', True, None)
        messages.success(self.request, phrases.base.saved)
        return result

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'event': self.request.event, 'user': self.object})
        return kwargs


class SpeakerPasswordReset(SpeakerViewMixin, ActionConfirmMixin, DetailView):
    permission_required = 'base.update_speakerprofile'
    model = User
    context_object_name = 'speaker'
    action_confirm_icon = 'key'
    action_confirm_label = phrases.base.password_reset_heading
    action_title = phrases.base.password_reset_heading
    action_text = _(
        'Do your really want to reset this user’s password? They won’t be able to log in until they set a new password.'
    )

    def action_object_name(self):
        user = self.get_object()
        return f'{user.get_display_name()} ({user.email})'

    def action_back_url(self):
        return self.get_object().event_profile(self.request.event).orga_urls.base

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        try:
            with transaction.atomic():
                user.reset_password(
                    event=getattr(self.request, 'event', None),
                    user=self.request.user,
                    orga=False,
                )
                messages.success(self.request, phrases.orga.password_reset_success)
        except SendMailException:  # pragma: no cover
            messages.error(self.request, phrases.orga.password_reset_fail)
        return redirect(user.event_profile(self.request.event).orga_urls.base)


class SpeakerToggleArrived(SpeakerViewMixin, View):
    permission_required = 'base.update_speakerprofile'

    def dispatch(self, request, event, code):
        self.profile.has_arrived = not self.profile.has_arrived
        self.profile.save()
        action = 'eventyay.speaker.arrived' if self.profile.has_arrived else 'eventyay.speaker.unarrived'
        self.object.log_action(
            action,
            data={'event': self.request.event.slug},
            user=self.request.user,
            # orga=True,
        )
        if url := self.request.GET.get('next'):
            if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
                return redirect(url)
        return redirect(self.profile.orga_urls.base)


class SpeakerInformationView(OrgaCRUDView):
    model = SpeakerInformation
    form_class = SpeakerInformationForm
    template_namespace = 'orga/speaker'
    context_object_name = 'information'

    def get_queryset(self):
        return self.request.event.information.all().prefetch_related('limit_tracks', 'limit_types').order_by('pk')

    def get_permission_required(self):
        permission_map = {'detail': 'orga_detail'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    def get_generic_title(self, instance=None):
        if self.action != 'list':
            return _('Speaker Information Note')
        return _('Speaker Information Notes')


class SpeakerExport(EventPermissionRequired, FormView):
    permission_required = 'base.update_event'
    template_name = 'orga/speaker/export.html'
    form_class = SpeakerExportForm

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result['event'] = self.request.event
        return result

    @context
    def exporters(self):
        return [exporter for exporter in get_schedule_exporters(self.request) if exporter.group == 'speaker']

    @context
    def tablist(self):
        return {
            'custom': _('CSV/JSON exports'),
            'general': _('More exports'),
            'api': _('API'),
        }

    def form_valid(self, form):
        result = form.export_data()
        if not result:
            messages.success(self.request, _('No data to be exported'))
            return redirect(self.request.path)
        return result


class SpeakerToggleFeatured(SpeakerViewMixin, View):
    permission_required = 'base.update_speakerprofile'

    def post(self, request, event, code):
        try:
            self.profile.is_featured = not self.profile.is_featured
            self.profile.save()
            action = 'eventyay.speaker.featured' if self.profile.is_featured else 'eventyay.speaker.unfeatured'
            self.profile.log_action(
                action,
                data={'event': self.request.event.slug},
                user=self.request.user,
            )
            return JsonResponse({'status': 'success', 'is_featured': self.profile.is_featured})
        except Exception as e:
            logger.error(f'Error toggling featured status for speaker {code}: {e}', exc_info=True)
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class SpeakerReorderView(EventPermissionRequired, View):
    permission_required = 'base.update_speakerprofile'

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            logger.warning('Invalid JSON in speaker reorder request')
            return JsonResponse({'status': 'error', 'message': 'Invalid request data'}, status=400)
        
        speaker_ids = data.get('speaker_ids', [])
        if not isinstance(speaker_ids, list):
            return JsonResponse({'status': 'error', 'message': 'Invalid request data'}, status=400)
        
        # Validate speaker_ids length to prevent abuse
        if len(speaker_ids) > 1000:  # Reasonable maximum
            logger.warning(f'Too many speaker IDs in reorder request: {len(speaker_ids)}')
            return JsonResponse({'status': 'error', 'message': 'Too many speakers'}, status=400)
        
        # Validate all speaker_ids belong to the current event
        valid_speaker_ids = set(
            SpeakerProfile.objects.filter(
                event=request.event,
                id__in=speaker_ids
            ).values_list('id', flat=True)
        )
        
        invalid_ids = set(speaker_ids) - valid_speaker_ids
        if invalid_ids:
            logger.warning(f'Invalid speaker IDs in reorder request: {invalid_ids}')
            return JsonResponse({'status': 'error', 'message': 'Invalid speaker IDs'}, status=400)
        
        try:
            with transaction.atomic():
                # Fetch all speakers for this event in their current global order
                all_speakers = list(
                    SpeakerProfile.objects.filter(
                        event=request.event
                    ).order_by('featured_order', 'id')
                )
                
                # Map IDs to speaker instances for quick lookup
                speakers_by_id = {speaker.id: speaker for speaker in all_speakers}
                
                # Determine the indices of the speakers being reordered
                moving_indices = [
                    index for index, speaker in enumerate(all_speakers)
                    if speaker.id in valid_speaker_ids
                ]
                
                # If none of the speakers are found (should not happen after validation), do nothing
                if not moving_indices:
                    return JsonResponse({'status': 'success'})
                
                start_index = min(moving_indices)
                end_index = max(moving_indices) + 1
                
                # Build the segment of speakers in the new order specified by speaker_ids
                reordered_segment = []
                for speaker_id in speaker_ids:
                    speaker = speakers_by_id.get(speaker_id)
                    if speaker is not None:
                        reordered_segment.append(speaker)
                
                # Prefix: speakers before the reordered segment
                prefix = all_speakers[:start_index]
                
                # Suffix: speakers after the reordered segment, excluding any that are being reordered
                suffix = [
                    speaker for speaker in all_speakers[end_index:]
                    if speaker.id not in valid_speaker_ids
                ]
                
                # Construct the final global sequence
                final_sequence = prefix + reordered_segment + suffix
                
                # Reassign order values globally to keep them contiguous and unique
                for index, speaker in enumerate(final_sequence):
                    speaker.featured_order = index
                
                # Bulk update all speakers in one query
                if final_sequence:
                    SpeakerProfile.objects.bulk_update(final_sequence, ['featured_order'])
            
            return JsonResponse({'status': 'success'})
        except (ValueError, TypeError) as e:
            logger.error(f'Error reordering speakers (data error): {e}')
            return JsonResponse({'status': 'error', 'message': 'Failed to save speaker order'}, status=400)
        except Exception as e:
            logger.error(f'Error reordering speakers (database error): {e}', exc_info=True)
            return JsonResponse({'status': 'error', 'message': 'Failed to save speaker order'}, status=500)
