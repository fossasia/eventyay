from django.contrib import messages
from django.db.models import Count
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from eventyay.base.header_presets import invalidate_preset_cache
from eventyay.base.models.event_header_preset import EventHeaderPreset, EventHeaderPresetCategory
from eventyay.control.forms.header_presets import (
    EventHeaderPresetCategoryForm,
    EventHeaderPresetForm,
)
from eventyay.control.permissions import AdministratorPermissionRequiredMixin


class HeaderPresetListView(AdministratorPermissionRequiredMixin, ListView):
    model = EventHeaderPreset
    template_name = 'pretixcontrol/admin/header_presets/list.html'
    context_object_name = 'presets'

    def get_queryset(self):
        return EventHeaderPreset.objects.select_related('category').order_by('category_id', 'id')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        categories = list(
            EventHeaderPresetCategory.objects.annotate(preset_count=Count('presets')).order_by('id')
        )
        current_category = self.request.GET.get('category', 'all').strip() or 'all'
        if current_category != 'all' and not current_category.isdigit():
            current_category = 'all'

        ctx['categories'] = categories
        ctx['current_category'] = current_category
        ctx['total_presets_count'] = len(ctx['presets'])
        return ctx


class HeaderPresetCreateView(AdministratorPermissionRequiredMixin, CreateView):
    model = EventHeaderPreset
    form_class = EventHeaderPresetForm
    template_name = 'pretixcontrol/admin/header_presets/form.html'
    success_url = reverse_lazy('eventyay_admin:admin.header_presets')

    def form_valid(self, form):
        messages.success(self.request, _('Header preset has been created successfully.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Could not create header preset. Please check the errors below.'))
        return super().form_invalid(form)


class HeaderPresetUpdateView(AdministratorPermissionRequiredMixin, UpdateView):
    model = EventHeaderPreset
    form_class = EventHeaderPresetForm
    template_name = 'pretixcontrol/admin/header_presets/form.html'
    success_url = reverse_lazy('eventyay_admin:admin.header_presets')

    def form_valid(self, form):
        messages.success(self.request, _('Header preset has been updated successfully.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Could not update header preset. Please check the errors below.'))
        return super().form_invalid(form)


class HeaderPresetDeleteView(AdministratorPermissionRequiredMixin, DeleteView):
    model = EventHeaderPreset
    template_name = 'pretixcontrol/admin/header_presets/delete.html'
    success_url = reverse_lazy('eventyay_admin:admin.header_presets')

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.delete()
        invalidate_preset_cache()
        messages.success(self.request, _('Header preset deleted successfully.'))
        return HttpResponseRedirect(success_url)

    def delete(self, request, *args, **kwargs):
        return self.form_valid(None)


class HeaderPresetCategoryCreateView(AdministratorPermissionRequiredMixin, CreateView):
    model = EventHeaderPresetCategory
    form_class = EventHeaderPresetCategoryForm
    template_name = 'pretixcontrol/admin/header_presets/category_form.html'
    success_url = reverse_lazy('eventyay_admin:admin.header_presets')

    def form_valid(self, form):
        messages.success(self.request, _('Preset category has been created successfully.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Could not create preset category. Please check the errors below.'))
        return super().form_invalid(form)


class HeaderPresetCategoryUpdateView(AdministratorPermissionRequiredMixin, UpdateView):
    model = EventHeaderPresetCategory
    form_class = EventHeaderPresetCategoryForm
    template_name = 'pretixcontrol/admin/header_presets/category_form.html'
    success_url = reverse_lazy('eventyay_admin:admin.header_presets')

    def form_valid(self, form):
        messages.success(self.request, _('Preset category has been updated successfully.'))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _('Could not update preset category. Please check the errors below.'))
        return super().form_invalid(form)


class HeaderPresetCategoryDeleteView(AdministratorPermissionRequiredMixin, DeleteView):
    model = EventHeaderPresetCategory
    template_name = 'pretixcontrol/admin/header_presets/category_delete.html'
    success_url = reverse_lazy('eventyay_admin:admin.header_presets')

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.delete()
        invalidate_preset_cache()
        messages.success(self.request, _('Preset category deleted successfully.'))
        return HttpResponseRedirect(success_url)

    def delete(self, request, *args, **kwargs):
        return self.form_valid(None)
