import json
import logging
from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DeleteView, UpdateView

from eventyay.base.models import Partner, SponsorGroup
from eventyay.control.permissions import EventPermissionRequiredMixin
from eventyay.eventyay_common.forms.partner import PartnerFormSet, SponsorGroupForm

logger = logging.getLogger(__name__)


class SponsorGroupCreateView(EventPermissionRequiredMixin, CreateView):
    """View for creating a new sponsor group"""
    model = SponsorGroup
    form_class = SponsorGroupForm
    template_name = 'eventyay_common/event/partner_group_form.html'
    permission = 'can_change_event_settings'
    
    def get_form_kwargs(self):
        """Pass event to the form"""
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs
    
    def form_valid(self, form):
        form.instance.event = self.request.event
        # Set order to be last
        max_order = SponsorGroup.objects.filter(
            event=self.request.event
        ).aggregate(Max('order'))['order__max'] or 0
        form.instance.order = max_order + 1
        return super().form_valid(form)
    
    def get_success_url(self):
        messages.success(self.request, _('Sponsor group created successfully.'))
        return reverse(
            'eventyay_common:event.update',
            kwargs={
                'organizer': self.request.organizer.slug,
                'event': self.request.event.slug
            }
        ) + '#partner-tab'


class SponsorGroupUpdateView(EventPermissionRequiredMixin, UpdateView):
    """View for updating a sponsor group"""
    model = SponsorGroup
    form_class = SponsorGroupForm
    template_name = 'eventyay_common/event/partner_group_form.html'
    permission = 'can_change_event_settings'
    context_object_name = 'sponsor_group'
    
    def get_form_kwargs(self):
        """Pass event to the form"""
        kwargs = super().get_form_kwargs()
        kwargs['event'] = self.request.event
        return kwargs
    
    def get_queryset(self):
        return SponsorGroup.objects.filter(event=self.request.event)
    
    def get_success_url(self):
        messages.success(self.request, _('Sponsor group updated successfully.'))
        return reverse(
            'eventyay_common:event.update',
            kwargs={
                'organizer': self.request.organizer.slug,
                'event': self.request.event.slug
            }
        ) + '#partner-tab'


class SponsorGroupDeleteView(EventPermissionRequiredMixin, DeleteView):
    """View for deleting a sponsor group"""
    model = SponsorGroup
    template_name = 'eventyay_common/event/partner_group_confirm_delete.html'
    permission = 'can_change_event_settings'
    context_object_name = 'sponsor_group'
    
    def get_queryset(self):
        return SponsorGroup.objects.filter(event=self.request.event)
    
    def get_success_url(self):
        messages.success(self.request, _('Sponsor group deleted successfully.'))
        return reverse(
            'eventyay_common:event.update',
            kwargs={
                'organizer': self.request.organizer.slug,
                'event': self.request.event.slug
            }
        ) + '#partner-tab'


class SponsorGroupReorderView(EventPermissionRequiredMixin, View):
    """AJAX view for reordering sponsor groups"""
    permission = 'can_change_event_settings'
    
    def post(self, request, *args, **kwargs):
        try:
            order_data = json.loads(request.body)
            group_ids = order_data.get('group_ids', [])
            
            with transaction.atomic():
                for index, group_id in enumerate(group_ids):
                    SponsorGroup.objects.filter(
                        id=group_id,
                        event=request.event
                    ).update(order=index)
            
            return JsonResponse({'status': 'success'})
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


class PartnerManageView(EventPermissionRequiredMixin, View):
    """View for managing partners within a sponsor group"""
    permission = 'can_change_event_settings'
    template_name = 'eventyay_common/event/partner_manage.html'
    
    def get_sponsor_group(self):
        return get_object_or_404(
            SponsorGroup,
            pk=self.kwargs['group_pk'],
            event=self.request.event
        )
    
    def get(self, request, *args, **kwargs):
        sponsor_group = self.get_sponsor_group()
        formset = PartnerFormSet(instance=sponsor_group, prefix='partners')
        
        return render(request, self.template_name, {
            'sponsor_group': sponsor_group,
            'formset': formset,
        })
    
    def post(self, request, *args, **kwargs):
        sponsor_group = self.get_sponsor_group()
        
        # Debug: Log the POST data
        logger.info(f"POST data keys: {list(request.POST.keys())}")
        logger.info(f"FILES data keys: {list(request.FILES.keys())}")
        logger.info(f"TOTAL_FORMS: {request.POST.get('partners-TOTAL_FORMS')}")
        logger.info(f"INITIAL_FORMS: {request.POST.get('partners-INITIAL_FORMS')}")
        
        # Log each form's data
        total_forms = int(request.POST.get('partners-TOTAL_FORMS', 0))
        for i in range(total_forms):
            name = request.POST.get(f'partners-{i}-name', '')
            logo = request.FILES.get(f'partners-{i}-logo')
            logger.info(f"Form {i}: name='{name}', has_logo={logo is not None}")
        
        formset = PartnerFormSet(
            request.POST,
            request.FILES,
            instance=sponsor_group,
            prefix='partners'
        )
        
        if formset.is_valid():
            instances = formset.save()
            logger.info(f"Saved {len(instances)} partner instances")
            for instance in instances:
                logger.info(f"Partner: {instance.name}, Logo: {instance.logo}, Logo Width: {instance.logo_width}")
            messages.success(request, _('Partners updated successfully.'))
            return redirect(
                reverse(
                    'eventyay_common:event.update',
                    kwargs={
                        'organizer': request.organizer.slug,
                        'event': request.event.slug
                    }
                ) + '#partner-tab'
            )
        else:
            logger.error(f"Formset validation failed: {formset.errors}")
            logger.error(f"Non-form errors: {formset.non_form_errors()}")
            messages.error(request, _('Please correct the errors below.'))
        
        return render(request, self.template_name, {
            'sponsor_group': sponsor_group,
            'formset': formset,
        })


class PartnerReorderView(EventPermissionRequiredMixin, View):
    """AJAX view for reordering partners within a group"""
    permission = 'can_change_event_settings'
    
    def post(self, request, *args, **kwargs):
        try:
            order_data = json.loads(request.body)
            partner_ids = order_data.get('partner_ids', [])
            group_id = order_data.get('group_id')  # Optional: for validation
            
            with transaction.atomic():
                for index, partner_id in enumerate(partner_ids):
                    # Validate that partner belongs to the event (and optionally to the group)
                    query = Partner.objects.filter(
                        id=partner_id,
                        sponsor_group__event=request.event
                    )
                    if group_id:
                        query = query.filter(sponsor_group_id=group_id)
                    
                    query.update(order=index)
            
            return JsonResponse({'status': 'success'})
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(f"Failed to reorder partners: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': _('Invalid request data')}, status=400)


class PartnerMoveView(EventPermissionRequiredMixin, View):
    """AJAX view for moving a partner to a different group"""
    permission = 'can_change_event_settings'
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            partner_id = data.get('partner_id')
            new_group_id = data.get('new_group_id')
            new_order = data.get('new_order', 0)
            
            with transaction.atomic():
                partner = get_object_or_404(
                    Partner,
                    id=partner_id,
                    sponsor_group__event=request.event
                )
                new_group = get_object_or_404(
                    SponsorGroup,
                    id=new_group_id,
                    event=request.event
                )
                
                partner.sponsor_group = new_group
                partner.order = new_order
                partner.save()
            
            return JsonResponse({'status': 'success'})
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(f"Failed to move partner: {str(e)}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': _('Invalid request data')}, status=400)
