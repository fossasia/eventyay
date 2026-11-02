import json

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import CreateView, DeleteView, TemplateView, UpdateView, View

from eventyay.base.forms.organizer_request import OrganizerRequestQuestionForm
from eventyay.base.models import OrganizerRequestFieldSetting, OrganizerRequestQuestion
from eventyay.base.organizer_request_fields import (
    REQUEST_FIELDS,
    next_form_position,
    organiser_form_rows,
    organizer_request_enabled,
    save_form_order,
)
from eventyay.base.settings import GlobalSettingsObject
from eventyay.control.permissions import AdministratorPermissionRequiredMixin


class OrganizerRequestQuestionList(AdministratorPermissionRequiredMixin, TemplateView):
    template_name = 'pretixcontrol/admin/organizer_requests/questions.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['field_rows'] = organiser_form_rows()
        context['field_order'] = ','.join(row['sort_id'] for row in context['field_rows'])
        context['organizer_request_enabled'] = organizer_request_enabled()
        return context


class OrganizerRequestFeatureToggle(AdministratorPermissionRequiredMixin, View):
    def post(self, request):
        enabled = request.POST.get('enabled') == 'on'
        GlobalSettingsObject().settings.set('organizer_request_enabled', enabled)
        messages.success(
            request,
            _('The public organiser request form has been {state}.').format(
                state=_('enabled') if enabled else _('disabled')
            ),
        )
        return redirect('eventyay_admin:admin.organizer_forms')


class OrganizerRequestFormOrder(AdministratorPermissionRequiredMixin, View):
    def post(self, request):
        tokens = [part for part in request.POST.get('order', '').split(',') if part]
        if save_form_order(tokens):
            messages.success(request, _('The question order has been saved.'))
        else:
            messages.error(request, _('The question order could not be saved. Reload the page and try again.'))
        return redirect('eventyay_admin:admin.organizer_forms')


class OrganizerRequestFieldUpdate(AdministratorPermissionRequiredMixin, View):
    def post(self, request, key):
        spec = next((field for field in REQUEST_FIELDS if field['key'] == key), None)
        if spec is None:
            raise Http404
        if spec['locked']:
            return JsonResponse({'error': _('This question stays on the form.')}, status=400)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': _('Could not read that change.')}, status=400)
        setting = get_object_or_404(OrganizerRequestFieldSetting, key=key)
        field_name = payload.get('field')
        value = payload.get('value')
        if field_name == 'active' and isinstance(value, bool):
            setting.active = value
        elif field_name == 'required' and value in ('required', 'optional'):
            setting.required = value == 'required'
        else:
            return JsonResponse({'error': _('Could not read that change.')}, status=400)
        setting.save(update_fields=['active', 'required'])
        return JsonResponse({'ok': True})


class OrganizerRequestQuestionToggle(AdministratorPermissionRequiredMixin, View):
    def post(self, request, pk):
        question = get_object_or_404(OrganizerRequestQuestion, pk=pk)
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': _('Could not read that change.')}, status=400)
        field_name = payload.get('field')
        value = payload.get('value')
        if field_name == 'active' and isinstance(value, bool):
            question.active = value
        elif field_name == 'required' and value in ('required', 'optional'):
            question.required = value == 'required'
        else:
            return JsonResponse({'error': _('Could not read that change.')}, status=400)
        question.save(update_fields=['active', 'required'])
        return JsonResponse({'ok': True})


class OrganizerRequestQuestionWriteMixin:
    form_class = OrganizerRequestQuestionForm
    template_name = 'pretixcontrol/admin/organizer_requests/question_form.html'
    success_url = reverse_lazy('eventyay_admin:admin.organizer_forms')

    def form_valid(self, form):
        messages.success(self.request, _('The question has been saved.'))
        return super().form_valid(form)


class OrganizerRequestQuestionCreate(
    AdministratorPermissionRequiredMixin, OrganizerRequestQuestionWriteMixin, CreateView
):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('New question')
        return context

    def form_valid(self, form):
        form.instance.position = next_form_position()
        return super().form_valid(form)


class OrganizerRequestQuestionEdit(
    AdministratorPermissionRequiredMixin, OrganizerRequestQuestionWriteMixin, UpdateView
):
    model = OrganizerRequestQuestion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Edit question')
        return context


class OrganizerRequestQuestionDelete(AdministratorPermissionRequiredMixin, DeleteView):
    model = OrganizerRequestQuestion
    template_name = 'pretixcontrol/admin/organizer_requests/question_delete.html'
    success_url = reverse_lazy('eventyay_admin:admin.organizer_forms')
    context_object_name = 'question'

    def form_valid(self, form):
        if self.object.answers.exists():
            messages.error(
                self.request,
                _('This question already has answers, so it cannot be deleted. Deactivate it instead.'),
            )
            return redirect(self.success_url)
        messages.success(self.request, _('The question has been deleted.'))
        return super().form_valid(form)
