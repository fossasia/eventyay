import json
from collections import OrderedDict

from django import forms
from django.dispatch import receiver
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _
from eventyay.base.forms import SecretKeySettingsField
from eventyay.base.signals import (logentry_display, register_global_settings,
                                 register_payment_providers,
                                 requiredaction_display)


@receiver(register_payment_providers, dispatch_uid="payment_paypal")
def register_payment_provider(sender, **kwargs):
    from .payment import Paypal
    return Paypal


@receiver(signal=logentry_display, dispatch_uid="paypal_logentry_display")
def pretixcontrol_logentry_display(sender, logentry, **kwargs):
    if logentry.action_type != 'eventyay.plugins.eventyay_paypal.event':
        return

    data = json.loads(logentry.data)
    event_type = data.get('event_type')
    text = None
    plains = {
        'PAYMENT.SALE.COMPLETED': _('Payment completed.'),
        'PAYMENT.SALE.DENIED': _('Payment denied.'),
        'PAYMENT.SALE.REFUNDED': _('Payment refunded.'),
        'PAYMENT.SALE.REVERSED': _('Payment reversed.'),
        'PAYMENT.SALE.PENDING': _('Payment pending.'),
    }

    if event_type in plains:
        text = plains[event_type]
    else:
        text = event_type

    if text:
        return _('PayPal reported an event: {}').format(text)


@receiver(signal=requiredaction_display, dispatch_uid="paypal_requiredaction_display")
def pretixcontrol_action_display(sender, action, request, **kwargs):
    if not action.action_type.startswith('eventyay.plugins.eventyay_paypal'):
        return

    data = json.loads(action.data)

    if action.action_type == 'eventyay.plugins.eventyay_paypal.refund':
        template = get_template('plugins/paypal/action_refund.html')
    elif action.action_type == 'eventyay.plugins.eventyay_paypal.overpaid':
        template = get_template('plugins/paypal/action_overpaid.html')
    elif action.action_type == 'eventyay.plugins.eventyay_paypal.double':
        template = get_template('plugins/paypal/action_double.html')

    ctx = {'data': data, 'event': sender, 'action': action}
    return template.render(ctx, request)


@receiver(register_global_settings, dispatch_uid='paypal_global_settings')
def register_global_settings(sender, **kwargs):
    return OrderedDict([
        ('payment_paypal_connect_client_id', forms.CharField(
            label=_('PayPal Connect: Client ID'),
            required=False,
        )),
        ('payment_paypal_connect_secret_key', SecretKeySettingsField(
            label=_('PayPal Connect: Secret key'),
            required=False,
        )),
        ('payment_paypal_connect_endpoint', forms.ChoiceField(
            label=_('PayPal Connect Endpoint'),
            initial='live',
            choices=(
                ('live', 'Live'),
                ('sandbox', 'Sandbox'),
            ),
        )),
    ])
