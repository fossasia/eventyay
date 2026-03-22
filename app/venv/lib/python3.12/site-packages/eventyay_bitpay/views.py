import hashlib
import json
import logging
import requests
import urllib.parse
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from eventyay.base.models import Order, OrderPayment, Quota
from eventyay.base.services.locking import LockTimeoutException
from eventyay.control.permissions import event_permission_required
from eventyay.multidomain.urlreverse import build_absolute_uri, eventreverse

from .models import ReferencedBitPayObject
from .payment import BitPay

logger = logging.getLogger(__name__)


@xframe_options_exempt
def redirect_view(request, *args, **kwargs):
    try:
        data = signing.loads(request.GET.get("data", ""), salt="safe-redirect")
    except signing.BadSignature:
        return HttpResponseBadRequest("Invalid parameter")

    if "go" in request.GET:
        if "session" in data:
            for k, v in data["session"].items():
                request.session[k] = v
        return redirect(data["url"])
    else:
        params = request.GET.copy()
        params["go"] = "1"
        r = render(
            request,
            "eventyay_bitpay/redirect.html",
            {
                "url": build_absolute_uri(
                    request.event, "plugins:eventyay_bitpay:redirect"
                )
                + "?"
                + urllib.parse.urlencode(params),
            },
        )
        r._csp_ignore = True
        return r


@csrf_exempt
@require_POST
def webhook(request, *args, **kwargs):
    event_json = json.loads(request.body.decode("utf-8"))
    if "data" not in event_json and "id" in event_json:
        objid = event_json["id"]
    else:
        objid = event_json["data"]["id"]
    try:
        rso = ReferencedBitPayObject.objects.select_related(
            "order", "order__event"
        ).get(reference=objid)
        if rso.order.event != request.event:
            return HttpResponse("Unable to detect event", status=200)
        rso.order.log_action("eventyay_bitpay.event", data=event_json)
        return process_invoice(rso.order, rso.payment, objid)
    except ReferencedBitPayObject.DoesNotExist:
        return HttpResponse("Unable to detect event", status=200)


def process_invoice(order, payment, invoice_id):
    prov = BitPay(order.event)
    src = prov.client.get_invoice(invoice_id)

    if not payment:
        payment = order.payments.filter(
            info__icontains=invoice_id,
            provider="bitpay",
        ).last()
    if not payment:
        payment = order.payments.create(
            state=OrderPayment.PAYMENT_STATE_CREATED,
            provider="bitpay",
            amount=Decimal(src["amount"]),
            info=json.dumps(src),
        )

    with transaction.atomic():
        order.refresh_from_db()
        payment.refresh_from_db()

        if src["status"] == "new":
            pass
        elif src["status"] in ("paid", "confirmed", "complete"):
            if payment.state in (
                OrderPayment.PAYMENT_STATE_CREATED,
                OrderPayment.PAYMENT_STATE_PENDING,
            ):
                try:
                    payment.confirm()
                except LockTimeoutException:
                    return HttpResponse("Lock timeout, please try again.", status=503)
                except Quota.QuotaExceededException:
                    return HttpResponse("Quota exceeded.", status=200)
        elif src["status"] == ("expired", "invalid"):
            if payment.state in (
                OrderPayment.PAYMENT_STATE_CREATED,
                OrderPayment.PAYMENT_STATE_PENDING,
            ):
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.info = json.dumps(src)
                payment.save()
                payment.order.log_action(
                    "eventyay.event.order.payment.failed",
                    {
                        "local_id": payment.local_id,
                        "provider": payment.provider,
                        "info": json.dumps(src),
                    },
                )
            elif order.state in OrderPayment.PAYMENT_STATE_CONFIRMED:
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.info = json.dumps(src)
                payment.save()
                payment.create_external_refund()
                payment.order.log_action(
                    "eventyay.event.order.payment.failed",
                    {
                        "local_id": payment.local_id,
                        "provider": payment.provider,
                        "info": json.dumps(src),
                    },
                )

    return HttpResponse(status=200)


@event_permission_required("can_change_event_settings")
@require_POST
def auth_disconnect(request, **kwargs):
    del request.event.settings.payment_bitpay_token
    request.event.settings.payment_bitpay__enabled = False
    messages.success(request, _("Your BitPay account has been disconnected."))

    return redirect(
        reverse(
            "control:event.settings.payment.provider",
            kwargs={
                "organizer": request.event.organizer.slug,
                "event": request.event.slug,
                "provider": "bitpay",
            },
        )
    )


class BitPayOrderView:
    def dispatch(self, request, *args, **kwargs):
        try:
            self.order = request.event.orders.get(code=kwargs["order"])
            if (
                hashlib.sha1(self.order.secret.lower().encode()).hexdigest()
                != kwargs["hash"].lower()
            ):
                raise Http404("")
        except Order.DoesNotExist:
            # Do a hash comparison as well to harden timing attacks
            if (
                "abcdefghijklmnopq".lower()
                == hashlib.sha1("abcdefghijklmnopq".encode()).hexdigest()
            ):
                raise Http404("")
            else:
                raise Http404("")
        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def pprov(self):
        return self.payment.payment_provider

    @property
    def payment(self):
        return get_object_or_404(
            self.order.payments,
            pk=self.kwargs["payment"],
            provider__istartswith="bitpay",
        )


@method_decorator(xframe_options_exempt, "dispatch")
class ReturnView(BitPayOrderView, View):
    def get(self, request, *args, **kwargs):
        with transaction.atomic():
            self.order.refresh_from_db()
            if self.order.status == Order.STATUS_PAID:
                return self._redirect_to_order()

            payment_data = self.payment.info_data
            process_invoice(self.order, self.payment, payment_data["id"])
            return self._redirect_to_order()

    def _redirect_to_order(self):
        if self.request.session.get("payment_bitpay_order_secret") != self.order.secret:
            messages.error(
                self.request,
                _(
                    "Sorry, there was an error in the payment process. Please check the link "
                    "in your emails to continue."
                ),
            )
            return redirect(eventreverse(self.request.event, "presale:event.index"))

        return redirect(
            eventreverse(
                self.request.event,
                "presale:event.order",
                kwargs={"order": self.order.code, "secret": self.order.secret},
            )
            + ("?paid=yes" if self.order.status == Order.STATUS_PAID else "")
        )


@event_permission_required("can_change_event_settings")
def auth_start(request, **kwargs):
    from btcpay import crypto  # improve performance at import time

    if request.event.settings.payment_bitpay_token:
        messages.error(request, _("You are already connected to BitPay."))
        return redirect(
            reverse(
                "control:event.settings.payment.provider",
                kwargs={
                    "organizer": request.event.organizer.slug,
                    "event": request.event.slug,
                    "provider": "bitpay",
                },
            )
        )
    request.session["payment_bitpay_auth_event"] = request.event.pk

    request.event.settings.payment_bitpay_pem = crypto.generate_privkey()

    pem = request.event.settings.payment_bitpay_pem
    sin = crypto.get_sin_from_pem(pem)
    if request.GET.get("url"):
        url = request.GET.get("url")
    else:
        url = (
            "https://test.bitpay.com" if "test" in request.GET else "https://bitpay.com"
        )
    try:
        r = requests.post(
            url + "/tokens",
            json={
                "label": settings.INSTANCE_NAME,
                "facade": "merchant",
                "id": sin,
            },
        )
    except requests.ConnectionError:
        messages.error(request, _("Communication with BitPay was not successful."))
    else:
        if r.status_code == 200:
            data = r.json()["data"][0]
            request.event.settings.payment_bitpay_token = data["token"]
            request.event.settings.payment_bitpay_url = url
            return redirect(
                url + "/api-access-request?pairingCode=" + data["pairingCode"]
            )
        messages.error(request, _("Communication with BitPay was not successful."))

    return redirect(
        reverse(
            "control:event.settings.payment.provider",
            kwargs={
                "organizer": request.event.organizer.slug,
                "event": request.event.slug,
                "provider": "bitpay",
            },
        )
    )
