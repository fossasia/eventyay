from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, UpdateView

from eventyay.base.models.privacy import ThirdPartyService
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
        response = super().form_valid(form)
        messages.success(self.request, _('Your changes have been saved.'))
        return response

    def form_invalid(self, form):
        messages.error(self.request, _('Your changes have not been saved, see below for errors.'))
        return super().form_invalid(form)


class ServiceCreate(AdministratorPermissionRequiredMixin, ServiceFormMixin, CreateView):
    def form_valid(self, form):
        # The form's uniqueness check cannot see a service another admin is
        # adding at the same moment, so the database has the final say.
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            form.add_error('name', _('A service with this identifier already exists.'))
            return self.form_invalid(form)


class ServiceUpdate(AdministratorPermissionRequiredMixin, ServiceFormMixin, UpdateView):
    def form_valid(self, form):
        # A plain save() falls back to an INSERT when its UPDATE matches no row,
        # which would bring back a service deleted while this form was open.
        try:
            form.instance.save(force_update=True)
        except ThirdPartyService.NotUpdated:
            messages.error(self.request, _('This service has been deleted in the meantime.'))
            return HttpResponseRedirect(self.get_success_url())
        self.object = form.instance
        messages.success(self.request, _('Your changes have been saved.'))
        return HttpResponseRedirect(self.get_success_url())


class ServiceDelete(AdministratorPermissionRequiredMixin, CompatDeleteView):
    model = ThirdPartyService
    template_name = 'pretixcontrol/admin/privacy_service_delete.html'
    context_object_name = 'service'
    success_url = reverse_lazy('eventyay_admin:admin.global.privacy')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        messages.success(request, _('The service has been deleted.'))
        return HttpResponseRedirect(self.get_success_url())
