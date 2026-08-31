from django.dispatch import receiver
from django.template.loader import get_template
from django.urls import resolve, reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.signals import register_payment_providers
from eventyay.control.signals import html_head, nav_event, nav_organizer

from .payment import BankTransfer


@receiver(register_payment_providers, dispatch_uid='payment_banktransfer')
def register_payment_provider(sender, **kwargs):
    return BankTransfer




@receiver(nav_organizer, dispatch_uid='payment_banktransfer_organav')
def control_nav_orga_import(sender, request=None, **kwargs):
    """
    Temporary disabled
    """
    return []


@receiver(html_head, dispatch_uid='banktransfer_html_head')
def html_head_presale(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    if url.namespace == 'plugins:banktransfer':
        template = get_template('pretixplugins/banktransfer/control_head.html')
        return template.render({})
    else:
        return ''
