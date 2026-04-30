import hashlib
import hmac
import json
import logging
import time

import requests
from requests import RequestException

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
        elapsed = time.time() - t
        if 200 <= resp.status_code <= 299:
            logger.info(
                "Chat webhook delivered to %s in %.2fs (HTTP %d)",
                webhook_url,
                elapsed,
                resp.status_code,
            )
        else:
            logger.warning(
                "Chat webhook to %s returned HTTP %d in %.2fs",
                webhook_url,
                resp.status_code,
                elapsed,
            )
    except RequestException:
        logger.exception(
            "Chat webhook to %s failed after %.2fs",
            webhook_url,
            time.time() - t,
        )
