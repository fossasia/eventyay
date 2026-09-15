from collections import OrderedDict

from django import forms
from django.core.files import File
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from eventyay.base.settings import settings_hierarkey
from eventyay.base.signals import register_global_settings, register_ticket_outputs

from .forms import CertificateFileField, validate_rsa_privkey


@receiver(register_ticket_outputs, dispatch_uid='output_passbook')
def register_ticket_output(sender, **kwargs):
    from .passbook import PassbookOutput

    return PassbookOutput


@receiver(register_global_settings, dispatch_uid='passbook_settings')
def register_global_settings_handler(sender, **kwargs):
    return OrderedDict(
        [
            (
                'passbook_team_id',
                forms.CharField(
                    label=_('Passbook team ID'),
                    required=False,
                ),
            ),
            (
                'passbook_pass_type_id',
                forms.CharField(
                    label=_('Passbook type'),
                    required=False,
                ),
            ),
            (
                'passbook_certificate_file',
                CertificateFileField(
                    label=_('Passbook certificate file'),
                    required=False,
                ),
            ),
            (
                'passbook_wwdr_certificate_file',
                CertificateFileField(
                    label=_('Passbook CA Certificate'),
                    help_text=_(
                        'You can download the current CA certificate from apple at '
                        'https://www.apple.com/certificateauthority/AppleWWDRCAG4.cer'
                    ),
                    required=False,
                ),
            ),
            (
                'passbook_key',
                forms.CharField(
                    label=_('Passbook secret key'),
                    required=False,
                    widget=forms.Textarea,
                    validators=[validate_rsa_privkey],
                ),
            ),
            (
                'passbook_key_password',
                forms.CharField(
                    label=_('Passbook key password'),
                    widget=forms.PasswordInput(render_value=True),
                    required=False,
                    help_text=_('Optional, only necessary if the key entered above requires a password to use.'),
                ),
            ),
        ]
    )


settings_hierarkey.add_default('passbook_certificate_file', None, File)
settings_hierarkey.add_default('passbook_wwdr_certificate_file', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_background', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_background2x', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_background3x', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_icon', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_icon2x', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_icon3x', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_logo', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_logo2x', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_logo3x', None, File)
