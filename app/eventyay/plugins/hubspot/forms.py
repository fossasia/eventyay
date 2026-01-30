from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SettingsForm


class HubSpotSettingsForm(SettingsForm):
    """
    Minimal HubSpot plugin settings form.
    
    Allows event organizers to enable the plugin and provide their API key.
    
    TODO: In a future PR, add a UI for configuring field mappings between
    OrderPosition attendee data and HubSpot contact properties.
    """
    
    plugin_hubspot_enabled = forms.BooleanField(
        label=_('Enable HubSpot sync'),
        help_text=_('When enabled, attendees will be synced to HubSpot when orders are paid.'),
        required=False,
    )
    
    plugin_hubspot_api_key = forms.CharField(
        label=_('HubSpot Private App Access Token'),
        help_text=_('Your HubSpot private app access token. Keep this secret!'),
        required=False,
        widget=forms.PasswordInput(render_value=True),
    )
