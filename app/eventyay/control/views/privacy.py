from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, ListView, UpdateView

from eventyay.base.models import LogEntry
from eventyay.base.models.privacy import ThirdPartyService
from eventyay.base.services.privacy_audit import (
    PRIVACY_ACTION_PREFIX,
    log_privacy_change,
    service_snapshot,
)
from eventyay.control.forms.privacy import ThirdPartyServiceForm
from eventyay.control.permissions import AdministratorPermissionRequiredMixin
from eventyay.helpers.compat import CompatDeleteView


class ServiceFormMixin:
    model = ThirdPartyService
    form_class = ThirdPartyServiceForm
    template_name = 'pretixcontrol/admin/privacy_service_form.html'
    context_object_name = 'service'

    def get_success_url(self):
        return reverse('eventyay_admin:admin.global.privacy') + '#services'

    def form_valid(self, form):
        messages.success(self.request, _('Your changes have been saved.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)


class ServiceCreate(AdministratorPermissionRequiredMixin, ServiceFormMixin, CreateView):
    def form_valid(self, form):
        response = super().form_valid(form)
        log_privacy_change(
            self.request.user, 'service.added', self.object,
            name=self.object.name, title=self.object.title, category=self.object.category,
        )
        return response


class ServiceUpdate(AdministratorPermissionRequiredMixin, ServiceFormMixin, UpdateView):
    def form_valid(self, form):
        before = service_snapshot(ThirdPartyService.objects.get(pk=self.object.pk))
        response = super().form_valid(form)
        after = service_snapshot(self.object)

        if before['enabled'] != after['enabled']:
            action = 'service.enabled' if after['enabled'] else 'service.disabled'
            log_privacy_change(self.request.user, action, self.object, name=self.object.name, title=self.object.title)

        changes = {
            field: {'old': before[field], 'new': after[field]}
            for field in before
            if field != 'enabled' and before[field] != after[field]
        }
        if changes:
            log_privacy_change(
                self.request.user, 'service.changed', self.object,
                name=self.object.name, title=self.object.title, changes=changes,
            )
        return response


class ServiceDelete(AdministratorPermissionRequiredMixin, CompatDeleteView):
    model = ThirdPartyService
    template_name = 'pretixcontrol/admin/privacy_service_delete.html'
    context_object_name = 'service'
    success_url = reverse_lazy('eventyay_admin:admin.global.privacy')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Logged before the delete so the entry can still point at the row's id.
        log_privacy_change(
            request.user, 'service.deleted', self.object,
            name=self.object.name, title=self.object.title, category=self.object.category,
        )
        self.object.delete()
        messages.success(request, _('The service has been deleted.'))
        return HttpResponseRedirect(self.get_success_url())


class PrivacyAuditLog(AdministratorPermissionRequiredMixin, ListView):
    template_name = 'pretixcontrol/admin/privacy_audit_log.html'
    context_object_name = 'entries'
    paginate_by = 50

    def get_queryset(self):
        return (
            LogEntry.objects.filter(action_type__startswith=PRIVACY_ACTION_PREFIX)
            .select_related('user')
            .order_by('-datetime', '-pk')
        )
