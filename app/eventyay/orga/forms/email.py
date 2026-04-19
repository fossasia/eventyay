from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SettingsForm

ENCRYPTED_PASSWORD_PLACEHOLDER = '*' * 24

SMTP_VENDOR_CHOICES = (
    ('smtp', _('SMTP server')),
    ('sendgrid', _('SendGrid')),
)


class CentralMailSettingsForm(SettingsForm):
    """
    Unified SMTP / email-gateway form for the event.

    Lives on the common settings page (Event Home › Settings › Email tab).
    Both the Tickets and Talks components share the gateway configured here
    via ``Event.get_mail_backend()``.

    Sender addresses (mail_from, mail_from_name) and other content-level
    settings remain on each component's own email page.
    """

    smtp_use_custom = forms.BooleanField(
        label=_('Use custom email gateway'),
        help_text=_(
            'When enabled, all event-related emails (Tickets and Talks) are sent via '
            'the gateway configured below instead of the platform default.'
        ),
        required=False,
    )
    email_vendor = forms.ChoiceField(
        label=_('Email gateway type'),
        choices=SMTP_VENDOR_CHOICES,
        widget=forms.RadioSelect,
        required=False,
        initial='smtp',
    )
    send_grid_api_key = forms.CharField(
        label=_('SendGrid API key'),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'SG.xxxxxxxx'}),
    )
    smtp_host = forms.CharField(
        label=_('SMTP hostname'),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'mail.example.org'}),
    )
    smtp_port = forms.IntegerField(
        label=_('SMTP port'),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 587, 465, 25 …'}),
    )
    smtp_username = forms.CharField(
        label=_('SMTP username'),
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'myuser@example.org'}),
    )
    smtp_password = forms.CharField(
        label=_('SMTP password'),
        required=False,
        widget=forms.PasswordInput(
            attrs={'autocomplete': 'new-password'},
            render_value=True,
        ),
    )
    smtp_use_tls = forms.BooleanField(
        label=_('Use STARTTLS'),
        help_text=_('Commonly enabled on port 587.'),
        required=False,
    )
    smtp_use_ssl = forms.BooleanField(
        label=_('Use SSL'),
        help_text=_('Commonly enabled on port 465.'),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        # ActionFromUrl / other mixins may inject kwargs that hierarkey
        # SettingsForm does not accept.
        kwargs.pop('read_only', None)
        super().__init__(*args, **kwargs)
        if self.fields['smtp_password'].initial:
            self.fields['smtp_password'].initial = ENCRYPTED_PASSWORD_PLACEHOLDER

    def clean(self):
        data = self.cleaned_data

        if not data.get('smtp_use_custom'):
            return data

        password = data.get('smtp_password')
        username = data.get('smtp_username')
        if password == ENCRYPTED_PASSWORD_PLACEHOLDER:
            data['smtp_password'] = self.initial.get('smtp_password', '')
        elif not password:
            if username:
                data['smtp_password'] = self.initial.get('smtp_password', '')
            else:
                data['smtp_password'] = ''
        elif not username:
            data['smtp_password'] = ''

        vendor = data.get('email_vendor', 'smtp')

        if vendor == 'sendgrid':
            if not data.get('send_grid_api_key'):
                self.add_error(
                    'send_grid_api_key',
                    ValidationError(_('An API key is required when using SendGrid.')),
                )
        else:
            if data.get('smtp_use_tls') and data.get('smtp_use_ssl'):
                self.add_error(
                    'smtp_use_tls',
                    ValidationError(
                        _('You can activate either SSL or STARTTLS, but not both at the same time.')
                    ),
                )

        return data
