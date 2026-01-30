from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import Event
from eventyay.control.views.event import (
    EventSettingsFormView,
    EventSettingsViewMixin,
)

from .forms import HubSpotSettingsForm


class HubSpotSettings(EventSettingsViewMixin, EventSettingsFormView):
    """
    Event settings view for configuring HubSpot plugin.
    """
    model = Event
    form_class = HubSpotSettingsForm
    template_name = 'hubspot/settings.html'
    permission = 'can_change_settings'

    def get_success_url(self) -> str:
        return reverse(
            'plugins:hubspot:settings',
            kwargs={
                'organizer': self.request.event.organizer.slug,
                'event': self.request.event.slug,
            },
        )
