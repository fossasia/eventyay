from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q
from django.db.models.expressions import OrderBy
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from urllib.parse import urlencode
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, FormView, ListView, View
from django_context_decorator import context
from django_scopes import scope

from eventyay.base.models import Answer, SpeakerProfile, User
from eventyay.base.models.base import CachedFile
from eventyay.base.models.information import SpeakerInformation
from eventyay.base.models.submission import Submission, SubmissionStates
from eventyay.base.services.orderimport import parse_csv
from eventyay.base.services.talkimport import import_speakers
from eventyay.base.views.tasks import AsyncAction
from eventyay.common.exceptions import SendMailException
from eventyay.common.image import gravatar_csp
from eventyay.common.text.phrases import phrases
from eventyay.common.views.generic import CreateOrUpdateView, OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionConfirmMixin,
    ActionFromUrl,
    EventPermissionRequired,
    ImportProcessRedirectMixin,
    Filterable,
    PaginationMixin,
    PermissionRequired,
    Sortable,
)
from eventyay.consts import SizeKey
from eventyay.orga.forms.importers import SpeakerImportProcessForm
from eventyay.person.forms import (
    SpeakerFilterForm,
    SpeakerInformationForm,
    SpeakerProfileForm,
)
from eventyay.person.social_link_mixin import SpeakerSocialLinksMixin
from eventyay.submission.forms import TalkQuestionsForm
from eventyay.talk_rules.person import is_only_reviewer
from eventyay.talk_rules.submission import limit_for_reviewers, speaker_profiles_for_user


class SpeakerList(EventPermissionRequired, Sortable, Filterable, PaginationMixin, ListView):
    template_name = 'orga/speaker/list.html'
    context_object_name = 'speakers'
    default_filters = ('user__email__icontains', 'user__fullname__icontains')
    sortable_fields = ('position', 'user__email', 'user__fullname', 'is_featured')
    default_sort_field = 'position'
    secondary_sort = {'position': ('user__fullname',), 'is_featured': ('position', 'user__fullname')}
    permission_required = 'base.orga_list_speakerprofile'

    def _speaker_list_ordering(self, *, descending=False):
        direction = (
            OrderBy(F('position'), descending=True, nulls_last=True)
            if descending
            else OrderBy(F('position'), nulls_last=True)
        )
        return (direction, 'user__fullname', 'pk')

    def sort_queryset(self, qs):
        sort_key = self.request.GET.get('sort') or ''
        if not sort_key or sort_key == 'default':
            sort_key = getattr(self, 'default_sort_field', None) or ''
        plain_key = sort_key[1:] if sort_key.startswith('-') else sort_key
        if plain_key == 'position':
            return qs.order_by(*self._speaker_list_ordering(descending=sort_key.startswith('-')))
        return super().sort_queryset(qs)

    def get_filter_form(self):
        with scope(event=self.request.event):
            any_arrived = SpeakerProfile.objects.filter(event=self.request.event, has_arrived=True).exists()
        return SpeakerFilterForm(self.request.GET, event=self.request.event, filter_arrival=any_arrived)

    def get_queryset(self):
        with scope(event=self.request.event):
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
            qs = qs.distinct()
            return self.sort_queryset(qs).prefetch_related(
                Prefetch(
                    'user__submissions',
                    queryset=self._speaker_sessions_queryset(),
                    to_attr='list_sessions',
                )
            )

    def _speaker_sessions_queryset(self):
        qs = (
            self.request.event.submissions.exclude(
                state__in=(SubmissionStates.DELETED, SubmissionStates.DRAFT),
            )
            .order_by('title')
        )
        if is_only_reviewer(self.request.user, self.request.event):
            qs = limit_for_reviewers(qs, self.request.event, self.request.user)
        return qs

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm('base.update_speakerprofile', request.event):
            raise Http404
        order = request.POST.get('order')
        if not order:
            return HttpResponse(status=400)
        if not self._save_speaker_order(order):
            return HttpResponse(status=400)
        return HttpResponse(status=204)

    def _save_speaker_order(self, order: str) -> bool:
        try:
            requested_ids = [int(pk) for pk in order.split(',') if pk]
        except ValueError:
            return False
        if not requested_ids or len(requested_ids) != len(set(requested_ids)):
            return False

        with transaction.atomic(), scope(event=self.request.event):
            profiles = list(
                speaker_profiles_for_user(self.request.event, self.request.user)
                .select_related('user')
                .order_by(*self._speaker_list_ordering())
            )
            profile_by_id = {profile.pk: profile for profile in profiles}
            valid_requested_ids = [pk for pk in requested_ids if pk in profile_by_id]
            if not valid_requested_ids:
                return False

            requested_set = set(valid_requested_ids)
            requested_iter = iter(valid_requested_ids)
            reordered_ids = []
            for profile in profiles:
                if profile.pk in requested_set:
                    reordered_ids.append(next(requested_iter))
                else:
                    reordered_ids.append(profile.pk)

            updates = []
            for position, profile_id in enumerate(reordered_ids):
                profile = profile_by_id[profile_id]
                if profile.position != position:
                    profile.position = position
                    updates.append(profile)

            if updates:
                SpeakerProfile.objects.bulk_update(updates, ['position'])
                from eventyay.agenda.views.utils import clear_schedule_caches

                clear_schedule_caches(self.request.event)

        return True


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
        if isinstance(self.object, SpeakerProfile):
            return self.object
        return self.object.event_profile(self.request.event)

    def get_permission_object(self):
        return self.profile

    @cached_property
    def permission_object(self):
        return self.get_permission_object()


@method_decorator(gravatar_csp(), name='dispatch')
class SpeakerDetail(SpeakerSocialLinksMixin, SpeakerViewMixin, ActionFromUrl, CreateOrUpdateView):
    template_name = 'orga/speaker/form.html'
    form_class = SpeakerProfileForm
    model = User
    permission_required = 'base.orga_list_speakerprofile'
    write_permission_required = 'base.update_speakerprofile'

    def get_success_url(self) -> str:
        return self.profile.orga_urls.base

    def get_social_links_profile(self):
        return self.profile

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_social_links_context())
        return context

    @transaction.atomic()
    def form_valid(self, form):
        if not self.social_media_formset_is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        result = super().form_valid(form)
        if not self.questions_form.is_valid():
            return self.get(self.request, *self.args, **self.kwargs)
        self.questions_form.save()
        self.save_social_media_formset(self.profile)
        if form.has_changed():
            form.instance.log_action('eventyay.user.profile.update', person=self.request.user, orga=True)
        if form.has_changed() or self.questions_form.has_changed() or (
            self.social_media_formset and self.social_media_formset.has_changed()
        ):
            self.request.event.cache.set('rebuild_schedule_export', True, None)
        messages.success(self.request, phrases.base.saved)
        return result

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'event': self.request.event, 'user': self.object})
        if not self.request.user.has_perm('base.orga_view_speaker_emails', self.request.event):
            kwargs['with_email'] = False
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
    permission_required = 'base.mark_arrived_speakerprofile'

    def post(self, request, *args, **kwargs):
        self.profile.has_arrived = not self.profile.has_arrived
        self.profile.save(update_fields=['has_arrived'])
        action = 'eventyay.speaker.arrived' if self.profile.has_arrived else 'eventyay.speaker.unarrived'
        self.object.log_action(
            action,
            data={'event': self.request.event.slug},
            user=self.request.user,
            # orga=True,
        )
        if url := self.request.GET.get('next'):
            if url_has_allowed_host_and_scheme(
                url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(url)
        return redirect(self.request.event.orga_urls.speakers)

    def get(self, request, *args, **kwargs):
        return redirect(self.profile.orga_urls.base)


class SpeakerToggleFeatured(SpeakerViewMixin, View):
    permission_required = 'base.update_speakerprofile'

    def post(self, request, *args, **kwargs):
        self.profile.is_featured = not self.profile.is_featured
        self.profile.save(update_fields=['is_featured'])
        action = 'eventyay.speaker.featured' if self.profile.is_featured else 'eventyay.speaker.unfeatured'
        self.object.log_action(
            action,
            data={'event': self.request.event.slug},
            user=self.request.user,
        )
        from eventyay.agenda.views.utils import clear_schedule_caches

        clear_schedule_caches(self.request.event)
        return HttpResponse()


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


class SpeakerImportProcessView(ImportProcessRedirectMixin, EventPermissionRequired, AsyncAction, FormView):
    permission_required = 'base.update_event'
    template_name = 'orga/speaker/import_process.html'
    form_class = SpeakerImportProcessForm
    task = import_speakers
    known_errortypes = ['ImportExecutionError']
    IMPORT_FILENAME = 'speaker_import.csv'

    import_process_url_name = 'settings.import_export.speakers_import_process'
    import_page_url_name = 'import_export_settings'
    import_target = 'speaker'

    @cached_property
    def import_settings_url(self):
        base = self.request.event.orga_urls.import_export_settings
        query = urlencode({'import_target': self.import_target})
        return f'{base}?{query}#tab-import'

    def dispatch(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return super().dispatch(request, *args, **kwargs)
        try:
            _ = self.file
        except Http404:
            messages.error(request, _('The uploaded CSV file is missing or expired. Please upload it again.'))
            return redirect(self.import_settings_url)
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def file(self):
        return get_object_or_404(
            CachedFile,
            pk=self.kwargs.get('file'),
            filename=self.IMPORT_FILENAME,
            session_key=self.request.session.session_key,
        )

    @cached_property
    def parsed(self):
        return parse_csv(self.file.file, settings.MAX_SIZE_CONFIG[SizeKey.UPLOAD_SIZE_CSV])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['headers'] = self.parsed.fieldnames if self.parsed else []
        kwargs['event'] = self.request.event
        kwargs['initial'] = self.request.event.settings.speaker_import_settings
        return kwargs

    @context
    def preview_rows(self):
        if not self.parsed:
            return []
        rows = []
        headers = self.parsed.fieldnames or []
        for i, row in enumerate(self.parsed):
            if i >= 5:
                break
            rows.append([row.get(h, '') for h in headers])
        return rows

    @context
    def headers(self):
        return self.parsed.fieldnames if self.parsed else []

    def get(self, request, *args, **kwargs):
        if 'async_id' in request.GET and settings.HAS_CELERY:
            return self.get_result(request)
        if not self.parsed:
            messages.error(request, _('Could not parse the uploaded CSV file.'))
            return redirect(self.import_settings_url)
        return FormView.get(self, request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.parsed:
            messages.error(request, _('Could not parse the uploaded CSV file.'))
            return redirect(self.import_settings_url)
        return FormView.post(self, request, *args, **kwargs)

    def form_valid(self, form):
        self.request.event.settings.speaker_import_settings = form.cleaned_data
        return self.do(
            self.request.event.pk,
            str(self.file.id),
            form.cleaned_data,
            self.request.LANGUAGE_CODE,
            self.request.user.pk,
        )

    def get_success_url(self, value):
        return self.import_settings_url

    def get_error_url(self):
        return self.import_settings_url

    def get_success_message(self, value):
        if isinstance(value, dict):
            msg = _('Speaker import complete: {created} created, {updated} updated, {skipped} skipped.').format(
                created=value.get('created', 0),
                updated=value.get('updated', 0),
                skipped=value.get('skipped', 0),
            )
            errors = value.get('errors', [])
            if errors:
                msg += ' ' + _('Errors: {errors}').format(errors='; '.join(str(e) for e in errors[:10]))
            return msg
        return _('The speaker import was successful.')
