import hashlib
import hmac
import json
import logging
import time

import requests
from requests import RequestException

from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, log_event
from eventyay.celery_app import app

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 5  # seconds


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
        resp = requests.post(
            webhook_url,
            data=body,
            headers=headers,
            timeout=WEBHOOK_TIMEOUT,
            allow_redirects=False,
        )
        elapsed_ms = int((time.time() - t) * 1000)
        if 200 <= resp.status_code <= 299:
            log_event('video', 'connection.post', OUTCOME_SUCCESS, status=resp.status_code, duration_ms=elapsed_ms, backend='chat_webhook')
        else:
            log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='http_error', status=resp.status_code, duration_ms=elapsed_ms, backend='chat_webhook')
            logger.warning('Chat webhook returned HTTP %s', resp.status_code)
    except RequestException:
        log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='request_error', duration_ms=int((time.time() - t) * 1000), backend='chat_webhook')
        logger.exception("Chat webhook delivery failed")
