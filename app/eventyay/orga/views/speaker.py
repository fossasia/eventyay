from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import now
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
from eventyay.orga.forms.importers import CSVImportForm
from eventyay.base.models import CachedFile
from eventyay.base.services.orderimport import parse_csv
from eventyay.orga.forms.importers import CSVImportForm, SpeakerImportProcessForm
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


class SpeakerList(EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView):
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    default_filters = ('user__email__icontains', 'user__fullname__icontains')
    sortable_fields = ('user__email', 'user__fullname')
    default_sort_field = 'user__fullname'
    permission_required = 'base.orga_list_speakerprofile'

    def get_filter_form(self):
        any_arrived = SpeakerProfile.objects.filter(event=self.request.event, has_arrived=True).exists()
        return SpeakerFilterForm(self.request.GET, event=self.request.event, filter_arrival=any_arrived)

    def get_queryset(self):
        qs = (
            speaker_profiles_for_user(self.request.event, self.request.user)
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
        qs = qs.order_by('id').distinct()
        return self.sort_queryset(qs)


class SpeakerViewMixin(PermissionRequired):
    def get_object(self):
        return get_object_or_404(
            User.objects.filter(profiles__in=speaker_profiles_for_user(self.request.event, self.request.user))
            .order_by('id')
            .distinct(),
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


class SpeakerImportStart(EventPermissionRequired, FormView):
    template_name = 'orga/speaker/import.html'
    permission_required = 'base.update_event'
    form_class = CSVImportForm

    def form_valid(self, form):
        uploaded = form.cleaned_data['file']
        cached_file = CachedFile.objects.create(
            expires=now() + timedelta(days=1),
            date=now(),
            filename=uploaded.name or 'import.csv',
            type='text/csv',
        )
        cached_file.file.save(uploaded.name or 'import.csv', uploaded)
        return redirect(
            reverse(
                'orga:speakers.import.process',
                kwargs={'event': self.request.event.slug, 'file': cached_file.id},
            )
        )

    def get_success_url(self):
        return self.request.event.orga_urls.speakers_import


class SpeakerImportProcess(EventPermissionRequired, FormView):
    template_name = 'orga/speaker/import_process.html'
    permission_required = 'base.update_event'
    form_class = SpeakerImportProcessForm

    def dispatch(self, request, *args, **kwargs):
        if not self.parsed_reader:
            self.cached_file.delete()
            messages.error(self.request, _("We've been unable to parse the uploaded file as a CSV file."))
            return redirect(self.get_start_url())
        return super().dispatch(request, *args, **kwargs)

    def get_start_url(self):
        return self.request.event.orga_urls.speakers_import

    @cached_property
    def cached_file(self):
        return get_object_or_404(CachedFile, pk=self.kwargs.get('file'), filename__endswith='.csv')

    @cached_property
    def parsed_reader(self):
        self.cached_file.file.open('rb')
        return parse_csv(self.cached_file.file, 1024 * 1024)

    @cached_property
    def _preview(self):
        if not self.parsed_reader:
            return [], False
        rows = []
        has_more = False
        for idx, row in enumerate(self.parsed_reader):
            if idx < 3:
                rows.append(row)
            else:
                has_more = True
                break
        return rows, has_more

    @property
    def sample_rows(self):
        return self._preview[0]

    @property
    def has_additional_rows(self):
        return self._preview[1]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        event = self.request.event
        initial = getattr(event.settings, 'speaker_import_settings', None) or {}
        kwargs.update(
            {
                'headers': self.parsed_reader.fieldnames if self.parsed_reader else [],
                'event': event,
                'initial': initial,
            }
        )
        return kwargs

    def form_valid(self, form):
        self.request.event.settings.speaker_import_settings = form.cleaned_data
        self.cached_file.delete()
        messages.info(
            self.request,
            _('Field mapping saved. Import processing will be added soon, please re-run once available.'),
        )
        return redirect(self.get_start_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            {
                'file': self.cached_file,
                'headers': self.parsed_reader.fieldnames if self.parsed_reader else [],
                'sample_rows': self.sample_rows,
                'has_more_rows': self.has_additional_rows,
                'header_count': len(self.parsed_reader.fieldnames) if self.parsed_reader and self.parsed_reader.fieldnames else 0,
            }
        )
        return ctx
