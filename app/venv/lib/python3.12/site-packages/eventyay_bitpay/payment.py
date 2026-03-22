from typing import Union

import hashlib
import json
import logging
import requests
from collections import OrderedDict
from django import forms
from django.core import signing
from django.http import HttpRequest
from django.template.loader import get_template
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _  # NoQA
from i18nfield.forms import I18nFormField, I18nTextInput
from i18nfield.strings import LazyI18nString
from json import JSONDecodeError
from eventyay.base.models import OrderPayment, OrderRefund
from eventyay.base.payment import BasePaymentProvider, PaymentException
from eventyay.multidomain.urlreverse import build_absolute_uri
from requests import RequestException

from .models import ReferencedBitPayObject

logger = logging.getLogger(__name__)


class BitPay(BasePaymentProvider):
    identifier = "bitpay"
    verbose_name = _("BitPay")

    @property
    def public_name(self):
        return str(
            self.settings.get("public_name", as_type=LazyI18nString) or _("Crypto")
        )

    def settings_content_render(self, request):
        if not self.settings.token:
            return (
                "<p>{}</p>"
                "<p>"
                "<a href='{}' target='_blank' class='btn btn-primary btn-lg'>{}</a> "
                "<a href='{}' target='_blank' class='btn btn-default btn-lg'>{}</a> "
                "</p>"
                "<p>{}</p>"
                "</form>"  # This is a hell of a hack, sorry…
                "<form class='form-inline' action='{}' method='GET' target='_blank'>"
                "<input type='text' name='url' class='form-control' value='https://btcpay.lightbo.lt'> "
                "<button class='btn btn-default'>{}</button>"
                "</form>"
                "<form>"
            ).format(
                _(
                    "To accept payments via BitPay, you will need an account at BitPay. By clicking on the "
                    "following button, you can connect eventyay to your BitPay account. A BitPay site will open in a new "
                    "tab. Return to this page and refresh it after you authorized the token at BitPay."
                ),
                reverse(
                    "plugins:eventyay_bitpay:auth.start",
                    kwargs={
                        "organizer": self.event.organizer.slug,
                        "event": self.event.slug,
                    },
                ),
                _("Connect with BitPay"),
                reverse(
                    "plugins:eventyay_bitpay:auth.start",
                    kwargs={
                        "organizer": self.event.organizer.slug,
                        "event": self.event.slug,
                    },
                )
                + "?test=1",
                _("Connect with test.bitpay.com"),
                _(
                    "Alternatively, you can connect with a third-party provider using a BitPay-compatible API. Enter "
                    "the URL here you want to connect to."
                ),
                reverse(
                    "plugins:eventyay_bitpay:auth.start",
                    kwargs={
                        "organizer": self.event.organizer.slug,
                        "event": self.event.slug,
                    },
                ),
                _("Start pairing"),
            )
        else:
            return (
                "<button formaction='{}' class='btn btn-danger'>{}</button>"
            ).format(
                reverse(
                    "plugins:eventyay_bitpay:auth.disconnect",
                    kwargs={
                        "organizer": self.event.organizer.slug,
                        "event": self.event.slug,
                    },
                ),
                _("Disconnect from BitPay"),
            )

    @property
    def settings_form_fields(self):
        if not self.settings.token:
            return {}
        d = OrderedDict(
            [
                ("url", forms.CharField(label=_("API URL"), disabled=True)),
                (
                    "public_name",
                    I18nFormField(
                        label=_("Payment method name"),
                        widget=I18nTextInput,
                        help_text=_(
                            "Since you can accept a variety of different Crypto coins with BitPay and BitPay-compatible "
                            "services, you can set the name of the payment method here to reflect the coins you are "
                            "actually accepting."
                        ),
                    ),
                ),
            ]
            + list(super().settings_form_fields.items())
        )

        d.move_to_end("public_name", last=False)
        d.move_to_end("_enabled", last=False)
        return d

    def redirect(self, request, url):
        if request.session.get("iframe_session", False):
            return (
                build_absolute_uri(request.event, "plugins:eventyay_bitpay:redirect")
                + "?data="
                + signing.dumps(
                    {
                        "url": url,
                        "session": {
                            "payment_bitpay_order_secret": request.session[
                                "payment_bitpay_order_secret"
                            ],
                        },
                    },
                    salt="safe-redirect",
                )
            )
        else:
            return str(url)

    def payment_form_render(self, request) -> str:
        template = get_template("eventyay_bitpay/checkout_payment_form.html")
        ctx = {"request": request, "event": self.event, "settings": self.settings}
        return template.render(ctx)

    def checkout_confirm_render(self, request) -> str:
        template = get_template("eventyay_bitpay/checkout_payment_confirm.html")
        ctx = {"request": request, "event": self.event, "settings": self.settings}
        return template.render(ctx)

    def checkout_prepare(self, request, total):
        return True

    def payment_is_valid_session(self, request):
        return True

    @property
    def test_mode_message(self):
        if "//test.bitpay.com" in self.settings.url:
            return _(
                "The BitPay plugin is operating in test mode. No money will actually be transferred."
            )
        return None

    @cached_property
    def client(self):
        from btcpay import BTCPayClient

        return BTCPayClient(
            host=self.settings.url,
            pem=self.settings.pem,
            tokens={"merchant": self.settings.token},
        )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        request.session["payment_bitpay_order_secret"] = payment.order.secret

        try:
            inv = self.client.create_invoice(
                {
                    "price": float(payment.amount),
                    "currency": self.event.currency,
                    "orderId": payment.order.full_code,
                    "transactionSpeed": "medium",
                    "extendedNotifications": "true",
                    "notificationURL": build_absolute_uri(
                        self.event, "plugins:eventyay_bitpay:webhook"
                    ),
                    "redirectURL": build_absolute_uri(
                        self.event,
                        "plugins:eventyay_bitpay:return",
                        kwargs={
                            "order": payment.order.code,
                            "payment": payment.pk,
                            "hash": hashlib.sha1(
                                payment.order.secret.lower().encode()
                            ).hexdigest(),
                        },
                    ),
                    # "buyer": {"email": "test@customer.com"},
                    "token": self.settings.token,
                }
            )
        except RequestException:
            logger.exception("Failure during bitpay payment.")
            raise PaymentException(
                _(
                    "We had trouble communicating with BitPay. Please try again and get in touch "
                    "with us if this problem persists."
                )
            )
        ReferencedBitPayObject.objects.get_or_create(
            order=payment.order, payment=payment, reference=inv["id"]
        )
        payment.info = json.dumps(inv)
        payment.save(update_fields=["info"])
        return self.redirect(request, inv["url"])

    def payment_pending_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("eventyay_bitpay/pending.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "order": payment.order,
        }
        return template.render(ctx)

    def payment_control_render(self, request: HttpRequest, payment: OrderPayment):
        template = get_template("eventyay_bitpay/control.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "payment_info": payment.info_data,
            "order": payment.order,
            "provname": self.verbose_name,
        }
        return template.render(ctx)

    abort_pending_allowed = True

    def payment_refund_supported(self, payment: OrderPayment):
        return True

    def payment_partial_refund_supported(self, payment: OrderPayment):
        return True

    def _refund(self, refund):
        from btcpay import crypto

        payload = json.dumps(
            {
                "token": refund.payment.info_data.get("token"),
                "amount": refund.payment.info_data.get("price"),
                "currency": refund.payment.info_data.get("currency"),
                "refundEmail": refund.order.email,
            }
        )
        uri = (
            self.client.host
            + "/invoices/"
            + refund.payment.info_data.get("id")
            + "/refunds"
        )
        xidentity = crypto.get_compressed_public_key_from_pem(self.client.pem)
        xsignature = crypto.sign(uri + payload, self.client.pem)
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "X-Identity": xidentity,
            "X-Signature": xsignature,
            "X-accept-version": "2.0.0",
        }
        try:
            response = requests.post(
                uri, data=payload, headers=headers, verify=self.client.verify
            )
        except Exception:
            logger.exception("Failure during bitpay refund.")
            raise PaymentException(
                _(
                    "We had trouble communicating with BitPay. Please try again and get in touch "
                    "with us if this problem persists."
                )
            )
        if not response.ok:
            try:
                e = response.json()["error"]
            except JSONDecodeError:
                e = response

            logger.exception("Failure during bitpay refund: {}".format(e))
            raise PaymentException(_("BitPay reported an error: {}").format(e))

    def execute_refund(self, refund: OrderRefund):
        try:
            self._refund(refund)
        except requests.exceptions.RequestException as e:
            logger.exception("BitPay error: %s" % str(e))
            raise PaymentException(
                _(
                    "We had trouble communicating with BitPay. Please try again and contact "
                    "support if the problem persists."
                )
            )
        else:
            refund.done()

    def shred_payment_info(self, obj: Union[OrderPayment, OrderRefund]):
        d = obj.info_data
        for k, v in list(d.items()):
            if v not in (
                "id",
                "status",
                "price",
                "currency",
                "invoiceTime",
                "paymentSubtotals",
                "paymentTotals",
                "transactionCurrency",
                "amountPaid",
            ):
                d[k] = "█"
        obj.info_data = d
        obj.save()

        for le in (
            obj.order.all_logentries()
            .filter(action_type="eventyay_bitpay.event")
            .exclude(data="")
        ):
            d = le.parsed_data
            if "data" in d:
                for k, v in list(d["data"].items()):
                    if v not in (
                        "id",
                        "status",
                        "price",
                        "currency",
                        "invoiceTime",
                        "paymentSubtotals",
                        "paymentTotals",
                        "transactionCurrency",
                        "amountPaid",
                    ):
                        d["data"][k] = "█"
                le.data = json.dumps(d)
                le.shredded = True
                le.save(update_fields=["data", "shredded"])
