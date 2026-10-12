from collections import OrderedDict

from django import forms
from django.core.files import File
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from eventyay.base.forms import SecretKeySettingsField
from eventyay.base.settings import settings_hierarkey
from eventyay.base.signals import register_global_settings, register_ticket_outputs
from eventyay.plugins.passbook.forms import CertificateFileField, PrivateKeyField


@receiver(register_ticket_outputs, dispatch_uid='output_passbook')
def register_ticket_output(sender, **kwargs):
    """Register the Passbook ticket output with the Eventyay ticket outputs signal."""
    from .ticketoutput import PassbookTicketOutput

    return PassbookTicketOutput


@receiver(register_global_settings, dispatch_uid='passbook_global_settings')
def register_passbook_global_settings(sender, **kwargs):
    """Register platform-wide Apple Wallet developer credential fields in global settings."""
    return OrderedDict(
        [
            (
                'passbook_team_id',
                forms.CharField(
                    label=_('Apple Developer Team ID (Passbook)'),
                    help_text=_(
                        'Your 10-character Apple Team ID. Found in your Apple Developer account membership.'
                    ),
                    required=False,
                ),
            ),
            (
                'passbook_pass_type_id',
                forms.CharField(
                    label=_('Apple Pass Type ID (Passbook)'),
                    help_text=_(
                        'Your registered Apple Pass Type Identifier, e.g. pass.org.eventyay.tickets.'
                    ),
                    required=False,
                ),
            ),
            (
                'passbook_certificate_file',
                CertificateFileField(
                    label=_('Apple Pass signing certificate file'),
                    help_text=_(
                        'Upload your Pass Type ID certificate in PEM or DER format.'
                    ),
                    required=False,
                ),
            ),
            (
                'passbook_wwdr_certificate_file',
                CertificateFileField(
                    label=_('Apple Worldwide Developer Relations CA certificate'),
                    help_text=_(
                        'Apple WWDR intermediate certificate (e.g. AppleWWDRCAG4.cer or PEM).'
                    ),
                    required=False,
                ),
            ),
            (
                'passbook_key',
                PrivateKeyField(
                    label=_('Apple Pass signing private key'),
                    help_text=_(
                        'The RSA private key in PEM format matching your pass certificate.'
                    ),
                    required=False,
                ),
            ),
            (
                'passbook_key_password',
                SecretKeySettingsField(
                    label=_('Pass signing private key password'),
                    help_text=_(
                        'Optional password for encrypted private keys.'
                    ),
                    required=False,
                ),
            ),
        ]
    )


settings_hierarkey.add_default('passbook_team_id', '', str)
settings_hierarkey.add_default('passbook_pass_type_id', '', str)
settings_hierarkey.add_default('passbook_certificate_file', None, File)
settings_hierarkey.add_default('passbook_wwdr_certificate_file', None, File)
settings_hierarkey.add_default('passbook_key', '', str)
settings_hierarkey.add_default('passbook_key_password', '', str)
settings_hierarkey.add_default('ticketoutput_passbook_certificate', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_wwdr_certificate', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_icon', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_logo', None, File)
settings_hierarkey.add_default('ticketoutput_passbook_background_color', '#1B4D6B', str)
settings_hierarkey.add_default('ticketoutput_passbook_foreground_color', '#FFFFFF', str)
settings_hierarkey.add_default('ticketoutput_passbook_label_color', '#D9E8F0', str)
