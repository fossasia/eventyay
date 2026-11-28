import hashlib
import hmac
import json
import logging
import time
import uuid

import requests
from requests import RequestException

from django.conf import settings
from django.utils.timezone import now

from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, log_event
from eventyay.celery_app import app
from eventyay.storage.external import normalize_url, resolve_public_addresses, send_pinned

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 5  # seconds


def sign_webhook_body(body, hmac_secret):
    """Return the ``X-Eventyay-Signature`` header value for ``body`` (str or bytes)."""
    if isinstance(body, str):
        body = body.encode()
    signature = hmac.new(hmac_secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={signature}"


def room_webhook_meta(room):
    """The ``meta.room`` object that identifies the sending room to a receiver."""
    return {"id": str(room.pk), "name": str(room.name)}


def build_system_message(room, kind, message, channel_id=None):
    """
    Build a webhook system message: a message about the connection itself.

    Receivers recognise it by ``message_type == "system"`` or the ``system-``
    prefix of ``message_id`` and never show it to an audience.
    """
    return {
        "message_id": f"system-{uuid.uuid4()}",
        "channel": str(channel_id) if channel_id else None,
        "timestamp": now().isoformat(),
        "screen_name": "",
        "sender_id": "",
        "centralauth_id": None,
        "centralauth_username": None,
        "message": message,
        "message_type": "system",
        "profile_img": None,
        "user_language": None,
        "meta": {"kind": kind, "room": room_webhook_meta(room)},
    }


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


def deliver_chat_webhook(payload, webhook_url, hmac_secret):
    """
    POST a signed payload to a chat webhook.

    Returns the HTTP status code of the response, or ``None`` if the receiver
    could not be reached.
    """
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    headers = {
        "Content-Type": "application/json",
        "X-Eventyay-Signature": sign_webhook_body(body, hmac_secret),
    }

    t = time.time()
    try:
        resp = post_webhook(webhook_url, body, headers)
        if resp is None:
            log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='blocked_url', backend='chat_webhook')
            logger.warning('Chat webhook URL does not resolve to a public address')
            return None
    except RequestException:
        log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='request_error', duration_ms=int((time.time() - t) * 1000), backend='chat_webhook')
        logger.exception("Chat webhook delivery failed")
        return None
    elapsed_ms = int((time.time() - t) * 1000)
    if 200 <= resp.status_code <= 299:
        log_event('video', 'connection.post', OUTCOME_SUCCESS, status=resp.status_code, duration_ms=elapsed_ms, backend='chat_webhook')
    else:
        log_event('video', 'connection.post', OUTCOME_FAILURE, error_code='http_error', status=resp.status_code, duration_ms=elapsed_ms, backend='chat_webhook')
        logger.warning('Chat webhook returned HTTP %s', resp.status_code)
    return resp.status_code


@app.task(bind=True, max_retries=0, acks_late=True)
def send_chat_webhook(self, payload, webhook_url, hmac_secret):
    """
    Fire-and-forget Celery task that POSTs a chat event payload to an
    external webhook URL with HMAC-SHA256 authentication.

    No retries by default — the consumer is expected to tolerate missed
    messages. Set max_retries > 0 if retry behaviour is desired later.
    """
    deliver_chat_webhook(payload, webhook_url, hmac_secret)
