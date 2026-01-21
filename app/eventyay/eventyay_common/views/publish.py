from django.urls import reverse
from django.views.generic import FormView
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from eventyay.control.views.event import EventPermissionRequiredMixin, EventSettingsViewMixin
from eventyay.eventyay_common.forms.publish import EventPublishForm

class EventPublishView(EventPermissionRequiredMixin, EventSettingsViewMixin, FormView):
    template_name = 'eventyay_common/event/publish.html'
    permission = 'can_change_event_settings'
    form_class = EventPublishForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.request.event
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _('Event status has been updated.'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('eventyay_common:event.publish', kwargs={
            'organizer': self.request.event.organizer.slug,
            'event': self.request.event.slug,
        })
