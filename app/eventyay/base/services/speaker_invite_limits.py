import hashlib
import logging
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

from eventyay.common.text.phrases import phrases


logger = logging.getLogger(__name__)

CFP_MAX_INVITE_SENDS_PER_HOUR = getattr(settings, 'CFP_MAX_INVITE_SENDS_PER_HOUR', 20)
CFP_MAX_INVITE_RESENDS = getattr(settings, 'CFP_MAX_INVITE_RESENDS', 3)


def get_invitation_resend_key(invitation):
    # Keyed by proposal and recipient, so revoking and re-inviting the same
    # address does not reset the count.
    email_hash = hashlib.sha256(invitation.email.lower().encode()).hexdigest()
    return f'cfp_invite_resend_count:{invitation.submission_id}:{email_hash}'


def get_invitation_resend_count(invitation):
    try:
        return int(cache.get(get_invitation_resend_key(invitation), 0) or 0)
    except Exception:
        return 0


def record_invitation_resend(invitation, limit):
    """Counts one resend of an invitation.

    Raises ValidationError if the resend limit is exceeded, or if the cache
    backend is unavailable (fails closed).
    """
    key = get_invitation_resend_key(invitation)
    try:
        count = 1 if cache.add(key, 1, timeout=90 * 86400) else cache.incr(key)
    except Exception:
        logger.exception('Could not increment invitation resend count for %s', invitation.pk)
        raise ValidationError(phrases.cfp.invite_limit_unavailable)
    if count > limit:
        raise ValidationError(phrases.cfp.invite_resend_limit_reached.format(count=limit))


def release_invitation_resend(invitation):
    """Gives back a resend whose email could not be delivered."""
    try:
        cache.decr(get_invitation_resend_key(invitation))
    except Exception:
        logger.exception('Could not release invitation resend count for %s', invitation.pk)


def get_user_rate_limit_key(user_id):
    hour_bucket = datetime.now(UTC).strftime('%Y%m%d%H')
    return f'cfp_invite_sends:{user_id}:{hour_bucket}'


def _is_rate_limit_exempt(user):
    if not user or not getattr(user, 'pk', None) or not getattr(user, 'is_authenticated', False):
        return True
    return getattr(user, 'is_administrator', False)


def validate_speaker_invite_rate_limit(user, limit=None):
    """Raises ValidationError if the user has no hourly invitation budget left."""
    if _is_rate_limit_exempt(user):
        return
    limit = limit if limit is not None else CFP_MAX_INVITE_SENDS_PER_HOUR
    try:
        count = int(cache.get(get_user_rate_limit_key(user.pk), 0) or 0)
    except Exception:
        logger.exception('Could not read speaker invite rate limit for user %s', user.pk)
        raise ValidationError(phrases.cfp.invite_limit_unavailable)
    if count >= limit:
        raise ValidationError(phrases.cfp.invite_rate_limit_reached)


def record_speaker_invite_send(user, amount=1, limit=None):
    """Atomically counts invitation sends against the user's hourly budget.

    Raises ValidationError if the budget is exceeded, or if the cache backend
    is unavailable (fails closed).
    """
    if _is_rate_limit_exempt(user):
        return
    limit = limit if limit is not None else CFP_MAX_INVITE_SENDS_PER_HOUR
    key = get_user_rate_limit_key(user.pk)
    try:
        count = amount if cache.add(key, amount, timeout=7200) else cache.incr(key, amount)
    except Exception:
        logger.exception('Could not record speaker invite rate limit for user %s', user.pk)
        raise ValidationError(phrases.cfp.invite_limit_unavailable)
    if count > limit:
        raise ValidationError(phrases.cfp.invite_rate_limit_reached)
