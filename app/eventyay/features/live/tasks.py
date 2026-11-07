import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
from urllib.parse import urlparse

import requests
from django.utils.timezone import now
from requests import RequestException

from eventyay.base.operational_logging import OUTCOME_FAILURE, OUTCOME_SUCCESS, log_event
from eventyay.celery_app import app


logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 5  # seconds


def is_private_url(url):
    """Check if a URL points to a private/localhost address (SSRF protection)."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return True
    if hostname in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
        return True
    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = info[4][0]
            if not ipaddress.ip_address(addr).is_global:
                return True
    except (socket.gaierror, ValueError):
        return True
    return False


def post_chat_webhook(payload, webhook_url, hmac_secret):
    """
    POSTs a chat event or system payload to an external webhook URL with HMAC-SHA256 authentication.

    Returns the HTTP response status code, or None on network error.
    """
    if is_private_url(webhook_url):
        logger.warning('Rejected chat webhook POST to private or unresolvable host: %s', urlparse(webhook_url).hostname)
        return None

    body = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    signature = hmac.new(hmac_secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'X-Eventyay-Signature': f'sha256={signature}',
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
            log_event(
                'video',
                'connection.post',
                OUTCOME_SUCCESS,
                status=resp.status_code,
                duration_ms=elapsed_ms,
                backend='chat_webhook',
            )
        else:
            log_event(
                'video',
                'connection.post',
                OUTCOME_FAILURE,
                error_code='http_error',
                status=resp.status_code,
                duration_ms=elapsed_ms,
                backend='chat_webhook',
            )
            logger.warning('Chat webhook returned HTTP %s', resp.status_code)
        return resp.status_code
    except RequestException:
        log_event(
            'video',
            'connection.post',
            OUTCOME_FAILURE,
            error_code='request_error',
            duration_ms=int((time.time() - t) * 1000),
            backend='chat_webhook',
        )
        logger.exception('Chat webhook delivery failed')
        return None


def send_room_system_message(room, kind='test', message=None, extra_meta=None):
    """
    Sends a system message for a room to its configured chat webhook URL.

    Returns the HTTP status code, or None on network error.
    Raises ValueError if no chat webhook is configured for the room.
    """
    webhook_url = None
    hmac_secret = None
    for module in room.module_config or []:
        if module.get('type') == 'chat.native':
            cfg = module.get('config', {})
            webhook_url = cfg.get('webhook_url')
            hmac_secret = cfg.get('webhook_hmac_secret')
            break

    if not webhook_url or not hmac_secret:
        raise ValueError('Room has no chat webhook configured.')

    channel_id = ''
    try:
        if hasattr(room, 'channel') and room.channel:
            channel_id = str(room.channel.id)
    except Exception:
        pass

    room_name = getattr(room, 'name', '')
    if isinstance(room_name, dict):
        room_name = next(iter(room_name.values()), '')

    meta = {
        'kind': kind,
        'room': {
            'id': str(room.id),
            'name': str(room_name),
        },
    }
    if extra_meta:
        meta.update(extra_meta)

    payload = {
        'message_id': f'system-{secrets.token_hex(16)}',
        'channel': channel_id,
        'timestamp': now().isoformat(),
        'screen_name': '',
        'sender_id': '',
        'centralauth_id': None,
        'centralauth_username': None,
        'message': message or f'Test event from Eventyay room {room_name}',
        'message_type': 'system',
        'profile_img': None,
        'user_language': None,
        'meta': meta,
    }

    return post_chat_webhook(payload, webhook_url, hmac_secret)


@app.task(bind=True, max_retries=0, acks_late=True)
def send_chat_webhook(self, payload, webhook_url, hmac_secret):
    """
    Fire-and-forget Celery task that POSTs a chat event payload to an
    external webhook URL with HMAC-SHA256 authentication.

    No retries by default — the consumer is expected to tolerate missed
    messages. Set max_retries > 0 if retry behaviour is desired later.
    """
    return post_chat_webhook(payload, webhook_url, hmac_secret)
