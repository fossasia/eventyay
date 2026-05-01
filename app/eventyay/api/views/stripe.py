import json
import logging
from decimal import Decimal

import stripe
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from eventyay.base.models import Order, OrderPayment, OrderRefund
from eventyay.base.services.orders import mark_order_refunded
from eventyay.eventyay_common.tasks import update_billing_invoice_information
from eventyay.helpers.stripe_utils import (
    get_stripe_secret_key,
    get_stripe_webhook_secret_key,
)

logger = logging.getLogger(__name__)


@csrf_exempt
def stripe_webhook_view(request):
    payload = request.body
    webhook_secret_key = get_stripe_webhook_secret_key()
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not sig_header:
        logger.error('Missing Stripe signature header')
        return HttpResponse('Missing signature', status=400)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret_key)
    except ValueError as e:
        logger.error('Error parsing payload: %s', str(e))
        return HttpResponse('Invalid payload', status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error('Error verifying webhook signature: %s', str(e))
        return HttpResponse('Invalid signature', status=400)

    if event.type == 'payment_intent.succeeded':
        invoice_id = event.data.object.get('metadata', {}).get('invoice_id')
        update_billing_invoice_information.delay(invoice_id=invoice_id)

    elif event.type == 'charge.refunded':
        charge = event.data.object
        metadata = charge.get('metadata', {})
        order_code = metadata.get('order')
        payment_id = metadata.get('payment')
        charge_id = charge.get('id')
        
        payment = None
        if order_code and payment_id:
            payment = OrderPayment.objects.filter(order__code=order_code, local_id=payment_id).first()

        if not payment:
            payment = OrderPayment.objects.filter(info__contains=charge_id).first()

        if payment:
            order = payment.order
            # Process each refund in the charge
            stripe_refunds = charge.get('refunds', {}).get('data', [])
            
            for sr in stripe_refunds:
                amount = Decimal(sr.get('amount')) / 100
                stripe_refund_id = sr.get('id')
                
                # Check if we already recorded this refund
                if not order.refunds.filter(info__contains=stripe_refund_id).exists():
                    order.refunds.create(
                        payment=payment,
                        source=OrderRefund.REFUND_SOURCE_EXTERNAL,
                        state=OrderRefund.REFUND_STATE_DONE,
                        amount=amount,
                        provider='stripe',
                        info=json.dumps({'id': stripe_refund_id, 'full_data': sr})
                    )
                    logger.info('Recorded refund of %s for order %s via Stripe webhook.', amount, order.code)

            # If the charge is fully refunded, mark the order as refunded (canceled)
            if charge.get('refunded'):
                try:
                    if order.status != Order.STATUS_CANCELED:
                        mark_order_refunded(order, user=None)
                        logger.info('Order %s marked as fully refunded (canceled) via Stripe webhook.', order.code)
                except Exception as e:
                    logger.error('Error marking order %s as refunded: %s', order.code, str(e))

    return HttpResponse('Success', status=200)
