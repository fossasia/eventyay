from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DeleteView, ListView
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.control.views import CreateView, UpdateView

from .forms import ExhibitorInfoForm
from .models import ExhibitorInfo, ExhibitorSettings, generate_booth_id


class SettingsView(EventPermissionRequiredMixin, ListView):
    model = ExhibitorInfo
    template_name = 'exhibitors/settings.html'
    context_object_name = 'exhibitors'
    permission = 'can_change_settings'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        settings = ExhibitorSettings.objects.get_or_create(event=self.request.event)[0]
        ctx['settings'] = settings
        ctx['default_fields'] = ['attendee_name', 'attendee_email']
        return ctx

    def post(self, request, *args, **kwargs):
        settings = ExhibitorSettings.objects.get_or_create(event=self.request.event)[0]

        # Get selected fields, excluding default fields
        allowed_fields = request.POST.getlist('exhibitors_access_voucher')

        # Update settings
        settings.allowed_fields = allowed_fields
        settings.exhibitors_access_mail_subject = request.POST.get('exhibitors_access_mail_subject', '')
        settings.exhibitors_access_mail_body = request.POST.get('exhibitors_access_mail_body', '')
        settings.save()

        messages.success(self.request, _('Settings have been saved.'))
        return redirect(request.path)


class ExhibitorListView(EventPermissionRequiredMixin, ListView):
    model = ExhibitorInfo
    permission = ('can_change_event_settings', 'can_view_orders')
    template_name = 'exhibitors/exhibitor_info.html'
    context_object_name = 'exhibitors'

    def get_queryset(self):
        return ExhibitorInfo.objects.filter(event=self.request.event)

    def get_success_url(self) -> str:
        return reverse('plugins:exhibition:index', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorCreateView(EventPermissionRequiredMixin, CreateView):
    model = ExhibitorInfo
    form_class = ExhibitorInfoForm
    template_name = 'exhibitors/add.html'
    permission = 'can_change_event_settings'

    def form_valid(self, form):
        form.instance.event = self.request.event

        # Only generate booth_id if none was provided
        if not form.cleaned_data.get('booth_id'):
            form.instance.booth_id = generate_booth_id(event=self.request.event)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'create'
        return context

    def get_success_url(self):
        return reverse('plugins:exhibition:info', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorEditView(EventPermissionRequiredMixin, UpdateView):
    model = ExhibitorInfo
    form_class = ExhibitorInfoForm
    template_name = 'exhibitors/add.html'
    permission = 'can_change_event_settings'

    def get_initial(self):
        initial = super().get_initial()
        obj = self.get_object()
        initial['lead_scanning_enabled'] = obj.lead_scanning_enabled
        return initial

    def form_valid(self, form):
        # generate booth_id if none provided and there isn't an existing one
        if not form.cleaned_data.get('booth_id') and not form.instance.booth_id:
            form.instance.booth_id = generate_booth_id(event=self.request.event)

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'edit'
        return context

    def get_success_url(self):
        return reverse('plugins:exhibition:info', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorDeleteView(EventPermissionRequiredMixin, DeleteView):
    model = ExhibitorInfo
    template_name = 'exhibitors/delete.html'
    permission = ('can_change_event_settings',)

    def get_success_url(self) -> str:
        return reverse('plugins:exhibition:info', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug
        })


class ExhibitorCopyKeyView(EventPermissionRequiredMixin, View):
    permission = ('can_change_event_settings',)

    def get(self, request, *args, **kwargs):
        exhibitor = get_object_or_404(ExhibitorInfo, pk=kwargs['pk'])
        response = HttpResponse(exhibitor.key)
        response['Content-Disposition'] = (
            'attachment; filename="password.txt"'
        )
        return response
