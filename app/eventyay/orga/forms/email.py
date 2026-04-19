from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SettingsForm


def multimail_validate(val):
    for addr in val.split(','):
        validate_email(addr.strip())

ENCRYPTED_PASSWORD_PLACEHOLDER = '*' * 24

SMTP_VENDOR_CHOICES = (
    ('smtp', _('SMTP server')),
    ('sendgrid', _('SendGrid')),
)


class CentralMailSettingsForm(SettingsForm):
    """Shared SMTP / email-gateway form; saves to event.settings for Event.get_mail_backend()."""

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
    test_email = forms.CharField(
        label=_('Send test email to'),
        help_text=_('Enter one or more addresses (comma-separated) to send a test message.'),
        validators=[multimail_validate],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('read_only', None)
        super().__init__(*args, **kwargs)
        if self.fields['smtp_password'].initial:
            self.fields['smtp_password'].initial = ENCRYPTED_PASSWORD_PLACEHOLDER

    def save(self, *args, **kwargs):
        f = self.fields.pop('test_email', None)
        try:
            return super().save(*args, **kwargs)
        finally:
            if f:
                self.fields['test_email'] = f

    @property
    def changed_data(self):
        data = super().changed_data
        return [d for d in data if d != 'test_email']

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
            if not data.get('smtp_host'):
                self.add_error(
                    'smtp_host',
                    ValidationError(_('A hostname is required when using a custom SMTP server.')),
                )
            if not data.get('smtp_port'):
                self.add_error(
                    'smtp_port',
                    ValidationError(_('A port number is required when using a custom SMTP server.')),
                )
            if data.get('smtp_use_tls') and data.get('smtp_use_ssl'):
                self.add_error(
                    'smtp_use_tls',
                    ValidationError(
                        _('You can activate either SSL or STARTTLS, but not both at the same time.')
                    ),
                )

        return data
