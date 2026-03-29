import logging

import stripe
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from eventyay.eventyay_common.tasks import update_billing_invoice_information
from eventyay.helpers.stripe_utils import (
    get_stripe_secret_key,
    get_stripe_webhook_secret_key,
)

logger = logging.getLogger(__name__)


@csrf_exempt
def stripe_webhook_view(request):
    stripe.api_key = get_stripe_secret_key()
    payload = request.body
    webhook_secret_key = get_stripe_webhook_secret_key()
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']

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
        if not invoice_id:
            logger.warning(
                'Skipping Celery task: invoice_id missing from Stripe webhook metadata '
                '(event_id=%s, type=%s). This event does not map to a system billing invoice.',
                event.id,
                event.type,
            )
        else:
            update_billing_invoice_information.delay(invoice_id=invoice_id)

    return HttpResponse('Success', status=200)
