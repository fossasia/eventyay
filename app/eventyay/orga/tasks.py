import logging
from datetime import UTC, datetime, timedelta

import jwt
from django.conf import settings

from eventyay.celery_app import app
from eventyay.common.utils.masks import EmailMasker


logger = logging.getLogger(__name__)


def generate_sso_token(user_email: str) -> str:
    jwt_payload = {
        'email': user_email,
        'has_perms': 'base.edit_schedule',
        'exp': datetime.now(UTC) + timedelta(hours=1),
        'iat': datetime.now(UTC),
    }
    jwt_token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm='HS256')
    logger.info('Generated SSO token for user: %s', EmailMasker(user_email))
    return jwt_token


def set_header_token(user_email: str) -> dict:
    token = generate_sso_token(user_email)
    # Define the headers, including the Authorization header with the Bearer token
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    return headers


@app.task(
    bind=True,
    name='eventyay.orga.trigger_public_schedule',
    max_retries=3,
    default_retry_delay=60,
)
def trigger_public_schedule(self, is_show_schedule: bool, event_slug: str, organizer_slug: str, user_email: str):
    # Before, this task called the 'eventyay-talk' server API, but because we have now merged
    # 'eventyay-tickets' and 'eventyay-talk' into the same app,
    # we should call a Python function directly.
    logger.info('Not implemented `trigger_public_schedule` yet.')
