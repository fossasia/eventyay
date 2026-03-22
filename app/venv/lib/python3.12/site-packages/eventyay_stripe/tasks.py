import logging
from urllib.parse import urlsplit

import stripe
from django.conf import settings

from eventyay.base.services.tasks import EventTask
from eventyay.celery_app import app
from eventyay.multidomain.urlreverse import get_event_domain

from .models import RegisteredApplePayDomain

logger = logging.getLogger(__name__)


def get_domain_for_event(event):
    domain = get_event_domain(event, fallback=True)
    if not domain:
        siteurlsplit = urlsplit(settings.SITE_URL)
        return siteurlsplit.hostname
    return domain


def get_stripe_account_key(prov):
    if prov.settings.connect_user_id:
        return prov.settings.connect_user_id
    else:
        return prov.settings.publishable_key


@app.task(base=EventTask, max_retries=5, default_retry_delay=1)
def stripe_verify_domain(event, domain):
    from .payment import StripeCreditCard

    prov = StripeCreditCard(event)
    account = get_stripe_account_key(prov)

    api_config = {
        'api_key': prov.settings.connect_secret_key or prov.settings.connect_test_secret_key
        if prov.settings.connect_client_id and prov.settings.connect_user_id
        else prov.settings.secret_key
    }

    if prov.settings.connect_client_id and prov.settings.connect_user_id:
        api_config['stripe_account'] = prov.settings.connect_user_id

    if RegisteredApplePayDomain.objects.filter(account=account, domain=domain).exists():
        return

    try:
        resp = stripe.ApplePayDomain.create(domain_name=domain, **api_config)
    except stripe.error.StripeError:
        logger.exception('Could not verify domain with Stripe')
    else:
        if resp.livemode:
            RegisteredApplePayDomain.objects.create(domain=domain, account=account)
