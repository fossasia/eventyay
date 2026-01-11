from django import forms
from django.utils.translation import gettext_lazy as _
from eventyay.base.models import Event
from eventyay.base.forms import I18nModelForm, SettingsForm

class EventPublishForm(SettingsForm):
    live = forms.BooleanField(
        label=_("Event is Live"),
        required=False,
        help_text=_("If checked, the event landing page will be publicly accessible."),
        widget=forms.CheckboxInput(attrs={'data-toggle': 'toggle'})
    )
    ticket_shop_enabled = forms.BooleanField(
        label=_("Enable Ticket Shop"),
        required=False,
        help_text=_("If checked, the ticket shop will be accessible to customers. If unchecked, the shop will be hidden/inactive even if the event is live."),
        widget=forms.CheckboxInput(attrs={'data-toggle': 'toggle'})
    )

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.event = kwargs.get('obj')
        super().__init__(*args, **kwargs)
        if self.event:
            self.fields['live'].initial = self.event.live
            # Default to True for backward compatibility (meaning live=shop live)
            # But technically if we are migrating, live=shop live.
            # So if event.live was True, both should be True.
            self.fields['ticket_shop_enabled'].initial = self.event.settings.get('ticket_shop_enabled', as_type=bool, default=True)

    def save(self):
        if 'live' in self.cleaned_data:
            self.event.live = self.cleaned_data['live']
            self.event.save(update_fields=['live'])
        
        if 'ticket_shop_enabled' in self.cleaned_data:
            self.event.settings.set('ticket_shop_enabled', self.cleaned_data['ticket_shop_enabled'])
