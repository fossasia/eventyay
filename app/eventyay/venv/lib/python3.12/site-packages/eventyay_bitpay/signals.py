import json
from django.dispatch import receiver
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _
from eventyay.base.signals import (
    logentry_display,
    register_payment_providers,
    requiredaction_display,
)


@receiver(register_payment_providers, dispatch_uid="payment_bitpay")
def register_payment_provider(sender, **kwargs):
    from .payment import BitPay

    return BitPay


@receiver(signal=logentry_display, dispatch_uid="bitpay_logentry_display")
def eventyaycontrol_logentry_display(sender, logentry, **kwargs):
    if logentry.action_type != "eventyay_bitpay.event":
        return

    data = json.loads(logentry.data)
    event_type = data.get("event", {}).get("name", "?")
    return _("BitPay reported an event: {}").format(event_type)


@receiver(signal=requiredaction_display, dispatch_uid="bitpay_requiredaction_display")
def eventyaycontrol_action_display(sender, action, request, **kwargs):
    if not action.action_type.startswith("eventyay_bitpay"):
        return

    data = json.loads(action.data)

    if action.action_type == "eventyay_bitpay.refund":
        template = get_template("eventyay_bitpay/action_refund.html")
    elif action.action_type == "eventyay_bitpay.overpaid":
        template = get_template("eventyay_bitpay/action_overpaid.html")

    ctx = {"data": data, "event": sender, "action": action}
    return template.render(ctx, request)
