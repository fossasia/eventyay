import hashlib
import hmac
import json
import logging
import time

import requests
from requests import RequestException

from django.conf import settings

from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, log_event
from eventyay.celery_app import app
from eventyay.storage.external import normalize_url, resolve_public_addresses, send_pinned

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 5  # seconds


def post_webhook(webhook_url, body, headers):
    """
    POST to the webhook URL and return the response, or ``None`` if the URL is refused.

    The URL is checked for private addresses when it is saved, but its hostname can
    resolve to a different address by the time a message is sent (DNS rebinding). So
    the hostname is resolved and checked again here, and the request connects to
    exactly the addresses that passed the check.
    """
    if settings.DEBUG:
        # Private targets are allowed in DEBUG, as when the URL is saved.
        return requests.post(
            webhook_url,
            data=body,
            headers=headers,
            timeout=WEBHOOK_TIMEOUT,
            allow_redirects=False,
        )
    url = normalize_url(webhook_url)
    addresses = resolve_public_addresses(url) if url else ()
    if not addresses:
        return None
    with requests.Session() as session:
        # Environment proxies would connect by hostname and bypass the pinned address.
        session.trust_env = False
        request = session.prepare_request(requests.Request('POST', url, data=body, headers=headers))
        response = send_pinned(session, request, addresses, WEBHOOK_TIMEOUT)
        response.close()
        return response


@app.task(bind=True, max_retries=0, acks_late=True)
def send_chat_webhook(self, payload, webhook_url, hmac_secret):
    """
    Fire-and-forget Celery task that POSTs a chat event payload to an
    external webhook URL with HMAC-SHA256 authentication.

    No retries by default — the consumer is expected to tolerate missed
    messages. Set max_retries > 0 if retry behaviour is desired later.
    """
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(
        hmac_secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Eventyay-Signature": f"sha256={signature}",
    }

    t = time.time()
    try:
        resp = post_webhook(webhook_url, body, headers)
        if resp is None:
            log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='blocked_url', backend='chat_webhook')
            logger.warning('Chat webhook URL does not resolve to a public address')
            return
        elapsed_ms = int((time.time() - t) * 1000)
        if 200 <= resp.status_code <= 299:
            log_event('video', 'connection.post', OUTCOME_SUCCESS, status=resp.status_code, duration_ms=elapsed_ms, backend='chat_webhook')
        else:
            log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='http_error', status=resp.status_code, duration_ms=elapsed_ms, backend='chat_webhook')
            logger.warning('Chat webhook returned HTTP %s', resp.status_code)
    except RequestException:
        log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='request_error', duration_ms=int((time.time() - t) * 1000), backend='chat_webhook')
        logger.exception("Chat webhook delivery failed")
