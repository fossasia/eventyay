from django import forms
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SettingsForm


class HubSpotSettingsForm(SettingsForm):
    """
    Minimal HubSpot plugin settings form for MVP.

    Includes only an enable toggle and API key. Configurable field mappings
    between attendee data and HubSpot properties will be added later.
    
    Note: The API key is stored as a plain string (not masked in the database)
    but rendered with masked input in the form via PasswordInput widget.
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
