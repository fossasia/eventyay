import json
import logging
from decimal import Decimal

import stripe
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from eventyay.base.models import Order, OrderPayment, OrderRefund
from eventyay.base.operational_logging import OUTCOME_FAILURE, log_event
from eventyay.base.services.orders import mark_order_refunded
from eventyay.eventyay_common.tasks import update_billing_invoice_information
from eventyay.helpers.stripe_utils import get_stripe_webhook_secret_key


logger = logging.getLogger(__name__)


def _stripe_object_to_dict(obj):
    """Safely convert a StripeObject or dict-like object to a Python dict.

    Stripe Python SDK >= 15.0 removes mapping methods (.get, .items, etc.) from StripeObject.
    Calling .to_dict() recursively converts StripeObject instances into standard Python dicts,
    ensuring forward compatibility with Stripe 15.x and backward compatibility with earlier versions.
    """
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    return {}


@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    """Billing Stripe webhook (API path ``/api/v1/webhook/stripe``).

    Payment-plugin ticket events use ``plugins:eventyay_stripe:webhook``
    (``/_stripe/webhook/``). This handler is for organiser billing invoices.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not sig_header:
        log_event('plugins', 'webhook.inbound', OUTCOME_FAILURE, error_code='missing_signature', backend='stripe')
        logger.error('Missing Stripe signature header')
        return HttpResponse('Missing signature', status=400)

    try:
        webhook_secret_key = get_stripe_webhook_secret_key()
    except ValidationError:
        log_event('plugins', 'webhook.inbound', OUTCOME_FAILURE, error_code='secret_unconfigured', backend='stripe')
        logger.exception('Stripe webhook secret is not configured')
        # 503: temporary misconfiguration — ask Stripe to retry after ops fixes secrets.
        return HttpResponse('Webhook secret not configured', status=503)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret_key)
    except ValueError as e:
        log_event('plugins', 'webhook.inbound', OUTCOME_FAILURE, error_code='invalid_payload', backend='stripe')
        logger.error('Error parsing payload: %s', e)
        return HttpResponse('Invalid payload', status=400)
    except stripe.error.SignatureVerificationError as e:
        log_event('plugins', 'webhook.inbound', OUTCOME_FAILURE, error_code='invalid_signature', backend='stripe')
        logger.error('Error verifying webhook signature: %s', e)
        return HttpResponse('Invalid signature', status=400)

    obj_data = _stripe_object_to_dict(getattr(event.data, 'object', None))

    if event.type == 'payment_intent.succeeded':
        metadata = obj_data.get('metadata') or {}
        invoice_id = metadata.get('invoice_id')
        # Non-billing PaymentIntents (and Stripe dashboard test events) omit
        # invoice_id; skip the Celery task instead of enqueueing a no-op.
        if invoice_id:
            update_billing_invoice_information.delay(invoice_id=invoice_id)
        else:
            logger.info(
                'Ignoring payment_intent.succeeded without invoice_id metadata (event %s)',
                getattr(event, 'id', None),
            )

    elif event.type == 'charge.refunded':
        charge = obj_data
        metadata = charge.get('metadata') or {}
        order_code = metadata.get('order')
        payment_id = metadata.get('payment')
        charge_id = charge.get('id')

        payment = None
        if order_code and payment_id:
            payment = OrderPayment.objects.filter(order__code=order_code, local_id=payment_id).first()

        if not payment and charge_id:
            payment = OrderPayment.objects.filter(info__contains=charge_id).first()

        if payment:
            order = payment.order
            # Process each refund in the charge
            refunds_container = charge.get('refunds') or {}
            stripe_refunds = refunds_container.get('data', []) if isinstance(refunds_container, dict) else []

            for sr in stripe_refunds:
                sr_data = _stripe_object_to_dict(sr)
                amount_val = sr_data.get('amount')
                if amount_val is not None:
                    amount = Decimal(str(amount_val)) / 100
                else:
                    amount = Decimal('0')
                stripe_refund_id = sr_data.get('id')

                # Check if we already recorded this refund
                if stripe_refund_id and not order.refunds.filter(info__contains=stripe_refund_id).exists():
                    order.refunds.create(
                        payment=payment,
                        source=OrderRefund.REFUND_SOURCE_EXTERNAL,
                        state=OrderRefund.REFUND_STATE_DONE,
                        amount=amount,
                        provider='stripe',
                        info=json.dumps({'id': stripe_refund_id, 'full_data': sr_data}),
                    )
                    logger.info('Recorded refund of %s for order %s via Stripe webhook.', amount, order.code)

            # If the charge is fully refunded, mark the order as refunded (canceled)
            if charge.get('refunded'):
                if order.status != Order.STATUS_CANCELED:
                    mark_order_refunded(order, user=None)
                    logger.info('Order %s marked as fully refunded (canceled) via Stripe webhook.', order.code)

    return HttpResponse('Success', status=200)
