from django.core.files import File
from django.dispatch import receiver

from eventyay.base.settings import settings_hierarkey
from eventyay.base.signals import register_ticket_outputs
from eventyay.plugins.passbook.ticketoutput import PassbookTicketOutput


@receiver(register_ticket_outputs, dispatch_uid='output_passbook')
def register_ticket_output(sender, **kwargs):
    return PassbookTicketOutput


for setting_name in (
    'ticketoutput_passbook_certificate',
    'ticketoutput_passbook_wwdr_certificate',
    'ticketoutput_passbook_icon',
    'ticketoutput_passbook_logo',
):
    settings_hierarkey.add_default(setting_name, None, File)
