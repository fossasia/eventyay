import http
import json
import logging
from collections import defaultdict

from csp.decorators import csp_update
from django.contrib import messages
from django.db import models, transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.forms.models import inlineformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import FormView, TemplateView, UpdateView, View
from django_context_decorator import context

from eventyay.cfp.flow import CfPFlow
from eventyay.common.forms import I18nFormSet
from eventyay.common.text.phrases import phrases
from eventyay.common.text.serialize import I18nStrJSONEncoder
from eventyay.common.views.generic import OrgaCRUDView
from eventyay.common.views.mixins import (
    ActionFromUrl,
    EventPermissionRequired,
    OrderActionMixin,
    PermissionRequired,
)
from eventyay.base.models import MailTemplateRoles
from eventyay.orga.forms import CfPForm, TalkQuestionForm, SubmissionTypeForm, TrackForm
from eventyay.orga.forms.cfp import (
    AccessCodeSendForm,
    AnswerOptionForm,
    CfPSettingsForm,
    QuestionFilterForm,
    ReminderFilterForm,
    SubmitterAccessCodeForm,
)
from eventyay.base.models import (
    AnswerOption,
    CfP,
    TalkQuestion,
    TalkQuestionRequired,
    TalkQuestionTarget,
    SubmissionType,
    SubmitterAccessCode,
    Track,
)
from eventyay.talk_rules.submission import questions_for_user

logger = logging.getLogger(__name__)


class CfPTextDetail(PermissionRequired, ActionFromUrl, UpdateView):
    form_class = CfPForm
    model = CfP
    template_name = 'orga/cfp/text.html'
    permission_required = 'base.update_event'
    write_permission_required = 'base.update_event'

    @context
    def tablist(self):
        return {
            'general': _('General information')
        }

    @context
    @cached_property
    def sform(self):
        return CfPSettingsForm(
            read_only=(self.action == 'view'),
            locales=self.request.event.locales,
            obj=self.request.event,
            data=self.request.POST if self.request.method == http.HTTPMethod.POST else None,
            prefix='settings',
        )

    @context
    @cached_property
    def different_deadlines(self):
        deadlines = defaultdict(list)
        for session_type in self.request.event.submission_types.filter(deadline__isnull=False):
            deadlines[session_type.deadline].append(session_type)
        deadlines.pop(self.request.event.cfp.deadline, None)
        if deadlines:
            return dict(deadlines)

    def get_object(self, queryset=None):
        return self.request.event.cfp

    def get_success_url(self) -> str:
        return self.object.urls.text

    @transaction.atomic
    def form_valid(self, form):
        if not self.sform.is_valid():
            messages.error(self.request, phrases.base.error_saving_changes)
            return self.form_invalid(form)
        messages.success(self.request, phrases.base.saved)
        form.instance.event = self.request.event
        result = super().form_valid(form)
        if form.has_changed():
            form.instance.log_action('eventyay.cfp.update', person=self.request.user, orga=True)
        self.sform.save()
        return result


class CfPForms(EventPermissionRequired, TemplateView):
    template_name = 'orga/cfp/forms.html'
    permission_required = 'base.update_event'

    @context
    @cached_property
    def sform(self):
        return CfPSettingsForm(
            read_only=False,
            locales=self.request.event.locales,
            obj=self.request.event,
            data=self.request.POST if self.request.method == http.HTTPMethod.POST else None,
            prefix='settings',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['generic_title'] = _('Forms')
        context['has_create_permission'] = True
        context['question_list'] = (
            questions_for_user(self.request, self.request.event, self.request.user)
            .annotate(answer_count=Count('answers'))
            .order_by('position')
        )
        context['create_url'] = reverse('orga:cfp.questions.create', kwargs={'event': self.request.event.slug})
        
        # Pass saved field order to template for JavaScript reordering
        fields_config = self.request.event.cfp.settings.get('fields_config', {})
        context['session_field_order'] = json.dumps(fields_config.get('session', []))
        context['speaker_field_order'] = json.dumps(fields_config.get('speaker', []))
        context['reviewer_field_order'] = json.dumps(fields_config.get('reviewer', []))
        
        sform = self.sform
        
        def get_field_data(targets, config_key):
            questions = TalkQuestion.all_objects.filter(
                event=self.request.event,
                target__in=targets
            )
            
            question_map = {str(q.id): q for q in questions if f'question_{q.pk}' in sform.fields}
            saved_order = fields_config.get(config_key, [])
            
            ordered_questions = []
            processed_ids = set()
            
            for item in saved_order:
                if item.isdigit() and item in question_map:
                    ordered_questions.append(question_map[item])
                    processed_ids.add(item)
            
            remaining_questions = sorted(
                [q for q_id, q in question_map.items() if q_id not in processed_ids],
                key=lambda x: (x.position, x.id)
            )
            ordered_questions.extend(remaining_questions)
            
            data = []
            for q in ordered_questions:
                data.append({
                    'question': q,
                    'field': sform[f'question_{q.pk}']
                })
            return data

        context['custom_session_fields'] = get_field_data([TalkQuestionTarget.SUBMISSION], 'session')
        context['custom_speaker_fields'] = get_field_data([TalkQuestionTarget.SPEAKER], 'speaker')
        context['custom_reviewer_fields'] = get_field_data([TalkQuestionTarget.REVIEWER], 'reviewer')
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # Handle drag-drop reordering (AJAX request with 'order' parameter)
        order_param = request.POST.get('order')
        if order_param:
            self._handle_field_reordering(order_param)
            return HttpResponse(status=204)  # No content response for AJAX
        
        # Handle regular form submission
        if self.sform.is_valid():
            self.sform.save()
            messages.success(request, phrases.base.saved)
            return redirect(request.path)
        messages.error(request, phrases.base.error_saving_changes)
        return self.get(request, *args, **kwargs)
    
    def _handle_field_reordering(self, order_str):
        """Handle field reordering for both default fields and custom questions."""
        order_list = order_str.split(',')
        event = self.request.event
        
        custom_question_ids = []
        for item in order_list:
            if item.isdigit():
                custom_question_ids.append(int(item))
        
        fields_config = event.cfp.settings.get('fields_config', {})
        
        session_keys = ['title', 'abstract', 'description', 'notes', 'track', 'duration', 
                       'content_locale', 'image', 'do_not_record']
        speaker_keys = ['biography', 'avatar', 'avatar_source', 'avatar_license', 'availabilities',
                       'additional_speaker']
        
        has_session_fields = any(item in session_keys for item in order_list)
        has_speaker_fields = any(item in speaker_keys for item in order_list)
        has_reviewer_fields = False

        if has_session_fields and has_speaker_fields:
            logger.warning(
                'Ambiguous field reordering: contains both session and speaker fields. '
                'Skipping fields_config update for event %s.',
                event.id
            )
            return

        target_type = None
        if not has_session_fields and not has_speaker_fields and custom_question_ids:
            all_speaker = True
            all_session = True
            all_reviewer = True
            valid_question_count = 0
            for qid in custom_question_ids:
                q = TalkQuestion.objects.filter(id=qid, event=event).first()
                if not q:
                    continue
                valid_question_count += 1
                if q.target != TalkQuestionTarget.SPEAKER:
                    all_speaker = False
                if q.target != TalkQuestionTarget.SUBMISSION:
                    all_session = False
                if q.target != TalkQuestionTarget.REVIEWER:
                    all_reviewer = False

            has_session_fields = all_session and valid_question_count > 0
            has_speaker_fields = all_speaker and valid_question_count > 0
            has_reviewer_fields = all_reviewer and valid_question_count > 0
        if has_session_fields:
            fields_config['session'] = order_list
            target_type = TalkQuestionTarget.SUBMISSION
        elif has_speaker_fields:
            fields_config['speaker'] = order_list
            target_type = TalkQuestionTarget.SPEAKER
        elif has_reviewer_fields:
            fields_config['reviewer'] = order_list
            target_type = TalkQuestionTarget.REVIEWER
        
        if target_type:
            for index, question_id in enumerate(custom_question_ids):
                try:
                    question = TalkQuestion.objects.get(id=question_id, event=event, target=target_type)
                    question.position = index
                    question.save(update_fields=['position'])
                except TalkQuestion.DoesNotExist:
                    logger.warning(
                        'Skipping missing TalkQuestion %s for event %s and target %s',
                        question_id,
                        event.id,
                        target_type,
                    )

        # Only save if changes were actually made
        if fields_config:
            event.cfp.settings['fields_config'] = fields_config
            event.cfp.save(update_fields=['settings'])

class QuestionView(OrderActionMixin, OrgaCRUDView):
    model = TalkQuestion
    form_class = TalkQuestionForm
    template_namespace = 'orga/cfp'
    context_object_name = 'question'
    detail_is_update = False

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        target = self.request.GET.get('target')
        if target:
            kwargs.setdefault('initial', {})
            kwargs['initial']['target'] = target
        return kwargs

    def get_queryset(self):
        return (
            questions_for_user(self.request, self.request.event, self.request.user)
            .annotate(answer_count=Count('answers'))
            .order_by('position')
        )

    def get_generic_title(self, instance=None):
        if instance:
            return (
                _('Custom field') + f' {phrases.base.quotation_open}{instance.question}{phrases.base.quotation_close}'
            )
        if self.action == 'create':
            return _('New custom field')
        return _('Custom fields')

    def get_permission_required(self):
        permission_map = {'list': 'orga_list', 'detail': 'orga_view'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    @cached_property
    def formset(self):
        formset_class = inlineformset_factory(
            TalkQuestion,
            AnswerOption,
            form=AnswerOptionForm,
            formset=I18nFormSet,
            can_delete=True,
            extra=0,
        )
        return formset_class(
            self.request.POST if self.request.method == http.HTTPMethod.POST else None,
            queryset=(
                AnswerOption.objects.filter(question=self.object) if self.object else AnswerOption.objects.none()
            ),
            event=self.request.event,
        )

    def save_formset(self, obj):
        if not self.formset.is_valid():
            return False
        for form in self.formset.initial_forms:
            if form in self.formset.deleted_forms:
                if not form.instance.pk:
                    continue
                obj.log_action(
                    'eventyay.question.option.delete',
                    person=self.request.user,
                    orga=True,
                    data={'id': form.instance.pk},
                )
                form.instance.delete()
                form.instance.pk = None
            elif form.has_changed():
                form.instance.question = obj
                form.save()
                change_data = {key: form.cleaned_data.get(key) for key in form.changed_data}
                change_data['id'] = form.instance.pk
                obj.log_action(
                    'eventyay.question.option.update',
                    person=self.request.user,
                    orga=True,
                    data=change_data,
                )

        extra_forms = [
            form for form in self.formset.extra_forms if form.has_changed and not self.formset._should_delete_form(form)
        ]
        for form in extra_forms:
            form.instance.question = obj
            form.save()
            change_data = {key: form.cleaned_data.get(key) for key in form.changed_data}
            change_data['id'] = form.instance.pk
            obj.log_action(
                'eventyay.question.option.create',
                person=self.request.user,
                orga=True,
                data=change_data,
            )

        return True

    @cached_property
    def filter_form(self):
        return QuestionFilterForm(self.request.GET, event=self.request.event)

    @cached_property
    def base_search_url(self):
        if not self.object or self.object.target == 'reviewer':
            return
        role = self.request.GET.get('role') or ''
        track = self.request.GET.get('track') or ''
        submission_type = self.request.GET.get('submission_type') or ''
        if self.object.target == 'submission':
            url = self.request.event.orga_urls.submissions + '?'
            if role == 'accepted':
                url = f'{url}state=accepted&state=confirmed&'
            elif role == 'confirmed':
                url = f'{url}state=confirmed&'
            if track:
                url = f'{url}track={track}&'
            if submission_type:
                url = f'{url}submission_type={submission_type}&'
        else:
            url = self.request.event.orga_urls.speakers + '?'
        return f'{url}&question={self.object.id}&'

    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)
        if 'form' in result:
            result['formset'] = self.formset
        if not self.object or not self.filter_form.is_valid():
            return result
        result.update(self.filter_form.get_question_information(self.object))
        result['grouped_answers_json'] = json.dumps(list(result['grouped_answers']), cls=I18nStrJSONEncoder)
        if self.action == 'detail':
            result['base_search_url'] = self.base_search_url
            result['filter_form'] = self.filter_form
        return result

    def form_valid(self, form):
        form.instance.event = self.request.event
        self.instance = form.instance
        
        is_new = not form.instance.pk
        if is_new:
            max_position = TalkQuestion.objects.filter(
                event=self.request.event,
                target=form.instance.target
            ).aggregate(models.Max('position'))['position__max']
            form.instance.position = (max_position or -1) + 1
        
        if form.cleaned_data.get('variant') in ('choices', 'multiple_choice'):
            changed_options = [form.changed_data for form in self.formset if form.has_changed()]
            if form.cleaned_data.get('options') and changed_options:
                messages.error(
                    self.request,
                    _('You cannot change the options and upload an option file at the same time.'),
                )
                return self.form_invalid(form)
        result = super().form_valid(form)
        
        if is_new:
            event = self.request.event
            fields_config = event.cfp.settings.get('fields_config', {})
            if form.instance.target == TalkQuestionTarget.SUBMISSION:
                config_key = 'session'
            elif form.instance.target == TalkQuestionTarget.SPEAKER:
                config_key = 'speaker'
            elif form.instance.target == TalkQuestionTarget.REVIEWER:
                config_key = 'reviewer'
            else:
                config_key = None
            
            if config_key:
                if config_key not in fields_config:
                    fields_config[config_key] = []
                if str(form.instance.pk) not in fields_config[config_key]:
                    fields_config[config_key].append(str(form.instance.pk))
                    event.cfp.settings['fields_config'] = fields_config
                    event.cfp.save(update_fields=['settings'])
        
        if form.cleaned_data.get('variant') in (
            'choices',
            'multiple_choice',
        ) and not form.cleaned_data.get('options'):
            formset = self.save_formset(self.instance)
            if not formset:
                return self.get(self.request, *self.args, **self.kwargs)
        return result

    def post(self, request, *args, **kwargs):
        order = request.POST.get('order')
        if not order:
            return super().post(request, *args, **kwargs)
        order = order.split(',')
        for index, pk in enumerate(order):
            option = get_object_or_404(
                self.object.options,
                pk=pk,
            )
            option.position = index
            option.save(update_fields=['position'])
        return self.get(request, *args, **kwargs)

    def perform_delete(self):
        try:
            with transaction.atomic():
                self.object.options.all().delete()
                self.object.logged_actions().delete()
                super().perform_delete()
        except ProtectedError:
            self.object.active = False
            self.object.save()
            messages.error(
                self.request,
                _('You cannot delete a custom field that has any responses. We have deactivated the field instead.'),
            )


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CfPQuestionToggle(PermissionRequired, View):
    """Toggle question field states via AJAX POST or legacy GET."""
    permission_required = 'base.update_talkquestion'

    def get_object(self) -> TalkQuestion:
        return get_object_or_404(
            TalkQuestion.all_objects,
            event=self.request.event,
            pk=self.kwargs.get('pk')
        )

    def dispatch(self, request, *args, **kwargs):
        # Check permissions first
        if not self.has_permission():
            return self.handle_no_permission()
            
        question = self.get_object()

        # Legacy GET: toggle active
        if request.method == http.HTTPMethod.GET:
            question.active = not question.active
            question.save(update_fields=['active'])
            return redirect(question.urls.base)

        # AJAX POST: toggle specific field
        if request.method == http.HTTPMethod.POST:
            return self._handle_post(request, question)

        return JsonResponse({'error': 'Method not allowed'}, status=405)

    @transaction.atomic
    def _handle_post(self, request, question):
        try:
            data = json.loads(request.body.decode())
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        field = data.get('field')
        value = data.get('value')

        # Validate that both field and value are present
        if field is None:
            return JsonResponse({'error': 'Missing field parameter'}, status=400)
        if value is None:
            return JsonResponse({'error': 'Missing value parameter'}, status=400)

        if field == 'active':
            # Validate type for boolean fields
            if not isinstance(value, bool):
                return JsonResponse({'error': 'Value must be boolean for active field'}, status=400)
            question.active = value
            question.save(update_fields=['active'])
        elif field == 'is_public':
            # Validate type for boolean fields
            if not isinstance(value, bool):
                return JsonResponse({'error': 'Value must be boolean for is_public field'}, status=400)
            question.is_public = value
            question.save(update_fields=['is_public'])
        elif field == 'question_required':
            # Validate type for string fields
            if not isinstance(value, str):
                return JsonResponse({'error': 'Value must be string for question_required field'}, status=400)
            allowed_values = [TalkQuestionRequired.OPTIONAL, TalkQuestionRequired.REQUIRED, TalkQuestionRequired.AFTER_DEADLINE]
            if value not in allowed_values:
                return JsonResponse({'error': 'Invalid value for question_required field'}, status=400)
            question.question_required = value
            question.save(update_fields=['question_required'])
        else:
            return JsonResponse({'error': f'Invalid field: {field}'}, status=400)

        return JsonResponse({'success': True, 'field': field, 'value': getattr(question, field)})


class CfPQuestionRemind(EventPermissionRequired, FormView):
    template_name = 'orga/cfp/question/remind.html'
    permission_required = 'base.orga_view_talkquestion'
    form_class = ReminderFilterForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs

    @staticmethod
    def get_missing_answers(*, questions, person, submissions):
        missing = []
        submissions = submissions.filter(speakers__in=[person])
        for question in questions:
            if question.target == TalkQuestionTarget.SUBMISSION:
                for submission in submissions:
                    answer = question.answers.filter(submission=submission).first()
                    if not answer or not answer.is_answered:
                        missing.append(question)
            elif question.target == TalkQuestionTarget.SPEAKER:
                answer = question.answers.filter(person=person).first()
                if not answer or not answer.is_answered:
                    missing.append(question)
        return missing

    @context
    def reminder_template(self):
        return self.request.event.get_mail_template(MailTemplateRoles.QUESTION_REMINDER)

    def form_invalid(self, form):
        messages.error(self.request, _('Could not send mails, error in configuration.'))
        return super().form_invalid(form)

    def form_valid(self, form):
        submissions = form.get_submissions()
        people = self.request.event.submitters.filter(submissions__in=submissions)
        questions = form.cleaned_data['questions'] or form.get_question_queryset()
        data = {
            'url': self.request.event.urls.user_submissions.full(),
        }
        for person in people:
            missing = self.get_missing_answers(questions=questions, person=person, submissions=submissions)
            if missing:
                data['questions'] = '\n'.join(f'- {question.question}' for question in missing)
                self.request.event.get_mail_template(MailTemplateRoles.QUESTION_REMINDER).to_mail(
                    person,
                    event=self.request.event,
                    context=data,
                    context_kwargs={'user': person},
                )
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.event.orga_urls.outbox


class SubmissionTypeView(OrderActionMixin, OrgaCRUDView):
    model = SubmissionType
    form_class = SubmissionTypeForm
    template_namespace = 'orga/cfp'

    def get_queryset(self):
        return self.request.event.submission_types.all().order_by('default_duration')

    def get_permission_required(self):
        permission_map = {'list': 'orga_list', 'detail': 'orga_detail'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    def get_generic_title(self, instance=None):
        if instance:
            return _('Session type') + f' {phrases.base.quotation_open}{instance.name}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New Session Type')
        return _('Session types')

    def delete_handler(self, request, *args, **kwargs):
        try:
            return super().delete_handler(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _('This Session Type is in use in a proposal and cannot be deleted.'),
            )
            return self.delete_view(request, *args, **kwargs)


class SubmissionTypeDefault(PermissionRequired, View):
    permission_required = 'base.update_submissiontype'

    def get_object(self):
        return get_object_or_404(self.request.event.submission_types, pk=self.kwargs.get('pk'))

    def dispatch(self, request, *args, **kwargs):
        super().dispatch(request, *args, **kwargs)
        submission_type = self.get_object()
        self.request.event.cfp.default_type = submission_type
        self.request.event.cfp.save(update_fields=['default_type'])
        submission_type.log_action('eventyay.submission_type.make_default', person=self.request.user, orga=True)
        messages.success(request, _('The Session Type has been made default.'))
        return redirect(self.request.event.cfp.urls.types)


class TrackView(OrderActionMixin, OrgaCRUDView):
    model = Track
    form_class = TrackForm
    template_namespace = 'orga/cfp'

    def get_queryset(self):
        return self.request.event.tracks.all()

    def get_permission_required(self):
        permission_map = {'list': 'orga_list', 'detail': 'orga_view'}
        permission = permission_map.get(self.action, self.action)
        return self.model.get_perm(permission)

    def get_generic_title(self, instance=None):
        if instance:
            return _('Track') + f' {phrases.base.quotation_open}{instance.name}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New track')
        return _('Tracks')

    def delete_handler(self, request, *args, **kwargs):
        try:
            return super().delete_handler(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _('This track is in use in a proposal and cannot be deleted.'),
            )
            return self.delete_view(request, *args, **kwargs)


class AccessCodeView(OrderActionMixin, OrgaCRUDView):
    model = SubmitterAccessCode
    form_class = SubmitterAccessCodeForm
    template_namespace = 'orga/cfp'
    context_object_name = 'access_code'
    lookup_field = 'code'
    path_converter = 'str'

    def get_queryset(self):
        return self.request.event.submitter_access_codes.all().order_by('valid_until')

    def get_generic_title(self, instance=None):
        if instance:
            return _('Access code') + f' {phrases.base.quotation_open}{instance.code}{phrases.base.quotation_close}'
        if self.action == 'create':
            return _('New access code')
        return _('Access codes')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if track := self.request.GET.get('track'):
            if track := self.request.event.tracks.filter(pk=track).first():
                kwargs['initial'] = kwargs.get('initial', {})
                kwargs['initial']['track'] = track
        return kwargs

    def delete_handler(self, request, *args, **kwargs):
        try:
            return super().delete_handler(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                _(
                    'This access code has been used for a proposal and cannot be deleted. To disable it, you can set its validity date to the past.'
                ),
            )
            return self.delete_view(request, *args, **kwargs)


class AccessCodeSend(PermissionRequired, UpdateView):
    model = SubmitterAccessCode
    form_class = AccessCodeSendForm
    context_object_name = 'access_code'
    template_name = 'orga/cfp/submitteraccesscode/send.html'
    permission_required = 'base.view_submitteraccesscode'

    def get_success_url(self) -> str:
        return self.request.event.cfp.urls.access_codes

    def get_object(self):
        return self.request.event.submitter_access_codes.filter(code__iexact=self.kwargs.get('code')).first()

    def get_permission_object(self):
        return self.get_object()

    def get_form_kwargs(self):
        result = super().get_form_kwargs()
        result['user'] = self.request.user
        return result

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, _('The access code has been sent.'))
        code = self.get_object()
        code.log_action(
            'eventyay.access_code.send',
            person=self.request.user,
            orga=True,
            data={'email': form.cleaned_data['to']},
        )
        return result

@method_decorator(csp_update({'SCRIPT_SRC': "'self' 'unsafe-eval'"}), name='dispatch')
class CfPFlowEditor(EventPermissionRequired, TemplateView):
    template_name = 'orga/cfp/flow.html'
    permission_required = 'base.update_event'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_configuration'] = self.request.event.cfp_flow.get_editor_config(json_compat=True)
        ctx['event_configuration'] = {
            'header_pattern': self.request.event.display_settings['header_pattern'] or 'bg-primary',
            'header_image': self.request.event.visible_header_image_url,
            'logo_image': self.request.event.visible_logo_url,
            'primary_color': self.request.event.visible_primary_color,
            'locales': self.request.event.locales,
        }
        return ctx

    def post(self, request, *args, **kwargs):
        # TODO: Improve validation
        try:
            data = json.loads(request.body.decode())
        except json.JSONDecodeError as e:
            logger.warning('Request body is not JSON: %s', e)
            return JsonResponse({'error': 'Invalid data'}, status=400)

        flow = CfPFlow(self.request.event)
        if 'action' in data and data['action'] == 'reset':
            flow.reset()
        else:
            logger.debug('Saving new CfP flow configuration: %s', data)
            flow.save_config(data)
        return JsonResponse({'success': True})
