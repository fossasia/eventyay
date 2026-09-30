"""Privacy-safe operational extras on the standard process logger.

``log_action`` remains the audit trail. This module mirrors allowlisted
actions onto ``logging.getLogger('eventyay.<area>')`` with datetime,
outcome, and correlation IDs. Prefer ``logger.exception`` for stack traces.
``log_event`` only adds allowlisted extra fields — it is not a second logging
system.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar
from typing import Final

OUTCOME_SUCCESS: Final = 'success'
OUTCOME_FAILURE: Final = 'failure'

_request_id: ContextVar[str | None] = ContextVar('eventyay_request_id', default=None)
_job_id: ContextVar[str | None] = ContextVar('eventyay_job_id', default=None)
_flag_eval_seen: ContextVar[frozenset[str] | None] = ContextVar('eventyay_flag_eval', default=None)

_SAFE_CORRELATION_ID = re.compile(r'^[A-Za-z0-9._-]{1,128}$')
_SAFE_ROUTE = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')

# Allowlisted extra fields that may appear on a log line. Anything else on the
# LogRecord (emails, tokens, payment info, request bodies) is ignored.
SAFE_LOG_FIELDS: Final[tuple[str, ...]] = (
    'component',
    'outcome',
    'action',
    'error_code',
    'event_id',
    'order_id',
    'order_code',
    'object_id',
    'user_id',
    'model',
    'voucher_id',
    'is_orga_action',
    'request_id',
    'job_id',
    'payment_provider',
    'payment_id',
    'payment_local_id',
    'checkin_list_id',
    'position_id',
    'duration_ms',
    'status',
    'route',
    'retry_count',
    'job_name',
    'mail_type',
    'recipient_count',
    'webhook_id',
    'backend',
    'flag_name',
    'occupancy',
    'smtp_code',
    'job_state',
)

# Keys copied from log_action data into process logs. Values must be opaque IDs
# or provider identifiers — never emails, secrets, or free-text payloads.
_SAFE_DATA_KEY_MAP: Final[dict[str, str]] = {
    'provider': 'payment_provider',
    'payment': 'payment_id',
    'local_id': 'payment_local_id',
    'list': 'checkin_list_id',
    'position': 'position_id',
    'order_code': 'order_code',
}

TICKETS_ACTION_PREFIXES: Final[tuple[str, ...]] = (
    'eventyay.event.order',
    'pretix.event.order',
    'eventyay.event.orders',
    'pretix.event.orders',
    'eventyay.event.checkin',
    'pretix.event.checkin',
    'eventyay.control.views.checkin',
    'pretix.control.views.checkin',
    'eventyay.voucher',
    'pretix.voucher',
    'eventyay.waitinglist',
    'pretix.waitinglist',
    'eventyay.event.item',
    'pretix.event.item',
    'eventyay.event.product',
    'pretix.event.product',
    'eventyay.event.category',
    'pretix.event.category',
    'eventyay.event.question',
    'pretix.event.question',
    'eventyay.event.quota',
    'pretix.event.quota',
    'eventyay.event.taxrule',
    'pretix.event.taxrule',
    'eventyay.event.tickets',
    'pretix.event.tickets',
    'eventyay.event.payment',
    'pretix.event.payment',
    'eventyay.event.live',
    'pretix.event.live',
    'eventyay.event.testmode',
    'pretix.event.testmode',
    'eventyay.event.private_testmode',
    'pretix.event.private_testmode',
    'eventyay.event.added',
    'pretix.event.added',
    'eventyay.event.changed',
    'pretix.event.changed',
    'eventyay.event.settings.changed',
    'eventyay.event.deleted',
    'pretix.event.deleted',
    'eventyay.event.meetup',
    'eventyay.property',
    'pretix.property',
    'eventyay.subevent',
    'pretix.subevent',
    'eventyay.event.checkinlist',
    'pretix.event.checkinlist',
    'eventyay.event.checkinlists',
    'pretix.event.checkinlists',
    'eventyay.giftcards',
    'pretix.giftcards',
    'eventyay.device',
    'pretix.device',
    'eventyay.gate',
    'pretix.gate',
    'eventyay.seatingplan',
    'pretix.seatingplan',
    'eventyay.plugins.ticketoutputpdf',
    'pretix.plugins.ticketoutputpdf',
    'eventyay.plugins.badges',
    'pretix.plugins.badges',
)

TALK_ACTION_PREFIXES: Final[tuple[str, ...]] = (
    'eventyay.submission',
    'eventyay.schedule',
    'eventyay.track',
    'eventyay.submission_type',
    'eventyay.access_code',
    'eventyay.speaker_information',
    'eventyay.tag',
    'eventyay.question',
    'eventyay.user.profile',
    'eventyay.user.password',
    'eventyay.user.token',
    'eventyay.cfp',
    'eventyay.speaker',
    'eventyay.event.update',
    'eventyay.event.talk_data',
)

VIDEO_ACTION_PREFIXES: Final[tuple[str, ...]] = (
    'eventyay.room',
    'eventyay.video',
    'eventyay.bbb',
    'bbbserver',
    'janusserver',
    'jitsiserver',
    'turnserver',
    'loungemeshserver',
    'event.adminaccess',
    'event.created',
    'event.updated',
    'event.cleared',
    'event.room',
    'event.tokens',
    'auth.user',
)

MAIL_ACTION_PREFIXES: Final[tuple[str, ...]] = (
    'eventyay.event.order.email',
    'pretix.event.order.email',
    'eventyay.mail',
    'eventyay.mail_template',
    'eventyay.plugins.sendmail',
    'eventyay.organizer.follower_notification',
)

PLUGINS_ACTION_PREFIXES: Final[tuple[str, ...]] = (
    'eventyay.event.plugins',
    'pretix.event.plugins',
    'eventyay.webhook',
    'pretix.webhook',
)

CORE_ACTION_PREFIXES: Final[tuple[str, ...]] = (
    'eventyay.control.auth',
    'pretix.control.auth',
    'eventyay.eventyay_common.auth',
    'eventyay.team',
    'pretix.team',
    'eventyay.invite',
    'eventyay.object.cloned',
    'eventyay.user.anonymized',
    'eventyay.user.settings.2fa',
    'eventyay.user.settings.notifications',
    'eventyay.user.settings',
    'eventyay.user.oauth',
    'eventyay.organizer',
    'pretix.organizer',
    'user.changed',
    'profile.changed',
)

AREA_PREFIXES: Final[dict[str, tuple[str, ...]]] = {
    'tickets': TICKETS_ACTION_PREFIXES,
    'talk': TALK_ACTION_PREFIXES,
    'video': VIDEO_ACTION_PREFIXES,
    'mail': MAIL_ACTION_PREFIXES,
    'plugins': PLUGINS_ACTION_PREFIXES,
    'core': CORE_ACTION_PREFIXES,
}

_PREFIX_MATCHERS: Final[tuple[tuple[str, str], ...]] = tuple(
    sorted(
        ((prefix, area) for area, prefixes in AREA_PREFIXES.items() for prefix in prefixes),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

# Skip high-volume or PII-heavy actions even when the prefix matches.
ACTION_SKIP_SUBSTRINGS: Final[tuple[str, ...]] = (
    'eventyay.event.order.comment',
    'pretix.event.order.comment',
    'eventyay.event.comment',
    'pretix.event.comment',
    'eventyay.organizer.settings',
    'pretix.organizer.settings',
    'chat.event',
    'auth.user.profile',
)
ACTION_SKIP_EXACT: Final[frozenset[str]] = frozenset(
    {
        'eventyay.device.updated',
        'pretix.device.updated',
        'eventyay.event.settings',
        'pretix.event.settings',
        'eventyay.event.action_required',
    }
)

# Tickets skip lists kept as aliases for existing tests.
TICKETS_ACTION_SKIP_SUBSTRINGS: Final[tuple[str, ...]] = ACTION_SKIP_SUBSTRINGS
TICKETS_ACTION_SKIP_EXACT: Final[frozenset[str]] = ACTION_SKIP_EXACT

_FAILURE_ACTION_MARKERS: Final[tuple[str, ...]] = (
    '.failed',
    '.denied',
    '.unknown',
    '.error',
)

_LOGGERS: Final[dict[str, logging.Logger]] = {
    area: logging.getLogger(f'eventyay.{area}') for area in AREA_PREFIXES
}

_signals_connected = False


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def sanitize_correlation_id(value: str | None) -> str:
    if value and _SAFE_CORRELATION_ID.fullmatch(value):
        return value
    return new_correlation_id()


def bind_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def reset_request_id() -> None:
    _request_id.set(None)
    _flag_eval_seen.set(None)


def get_request_id() -> str | None:
    return _request_id.get()


def bind_job_id(job_id: str) -> None:
    _job_id.set(job_id)


def reset_job_id() -> None:
    _job_id.set(None)
    _flag_eval_seen.set(None)


def get_job_id() -> str | None:
    return _job_id.get()


def is_safe_identifier(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return bool(_SAFE_CORRELATION_ID.fullmatch(value))
    return False


def is_safe_route(value: object) -> bool:
    return isinstance(value, str) and bool(_SAFE_ROUTE.fullmatch(value))


def safe_fields_from_log_data(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        return {}
    fields: dict[str, object] = {}
    for source_key, dest_key in _SAFE_DATA_KEY_MAP.items():
        if source_key not in data:
            continue
        value = data[source_key]
        if is_safe_identifier(value):
            fields[dest_key] = value
    return fields


def component_for_action(action: str) -> str | None:
    if action in ACTION_SKIP_EXACT:
        return None
    if any(marker in action for marker in ACTION_SKIP_SUBSTRINGS):
        return None
    for prefix, area in _PREFIX_MATCHERS:
        if action == prefix or action.startswith(prefix + '.'):
            return area
    return None


def is_tickets_action(action: str) -> bool:
    return component_for_action(action) == 'tickets'


def outcome_for_action(action: str) -> str:
    for marker in _FAILURE_ACTION_MARKERS:
        if marker in action:
            return OUTCOME_FAILURE
    return OUTCOME_SUCCESS


def logger_extra(
    component: str,
    action: str,
    outcome: str,
    **fields: object,
) -> dict[str, object]:
    """Allowlisted extras for ``logging.getLogger('eventyay.<area>')``."""
    extra = {
        'component': component,
        'outcome': outcome,
        'action': action,
        'request_id': get_request_id(),
        'job_id': get_job_id(),
    }
    for key, value in fields.items():
        if value is None or value == '':
            continue
        if key not in SAFE_LOG_FIELDS:
            continue
        if key == 'route':
            if is_safe_route(value):
                extra[key] = value
            continue
        if key in ('error_code', 'backend', 'job_name', 'mail_type', 'flag_name', 'job_state', 'model') and not is_safe_identifier(value):
            extra[key] = 'unknown' if key == 'backend' else 'invalid'
            continue
        extra[key] = value
    return extra


def log_event(
    component: str,
    action: str,
    outcome: str,
    *,
    level: int | None = None,
    error_code: str | None = None,
    event_id: int | None = None,
    order_id: int | None = None,
    order_code: str | None = None,
    object_id: int | str | None = None,
    user_id: int | None = None,
    model: str | None = None,
    voucher_id: int | None = None,
    is_orga_action: bool | None = None,
    **fields: object,
) -> None:
    """``logger.log`` with allowlisted extra fields. Prefer ``logger.exception`` for stack traces."""
    if level is None:
        level = logging.WARNING if outcome == OUTCOME_FAILURE else logging.INFO
    extra = logger_extra(
        component,
        action,
        outcome,
        error_code=error_code,
        event_id=event_id,
        order_id=order_id,
        order_code=order_code,
        object_id=object_id,
        user_id=user_id,
        model=model,
        voucher_id=voucher_id,
        is_orga_action=True if is_orga_action else None,
        **fields,
    )
    logger = _LOGGERS.get(component) or logging.getLogger(f'eventyay.{component}')
    try:
        logger.log(level, action, extra=extra)
    except Exception:
        return


def log_flag_evaluation(flag_name: str, enabled: bool) -> None:
    if enabled or not is_safe_identifier(flag_name):
        return
    seen = set(_flag_eval_seen.get() or ())
    if flag_name in seen:
        return
    seen.add(flag_name)
    _flag_eval_seen.set(frozenset(seen))
    log_event('video', 'video.feature_flag', OUTCOME_FAILURE, error_code='disabled', flag_name=flag_name)


def fields_from_action_name(action: str) -> dict[str, object]:
    marker = '.payment.provider.'
    if marker not in action:
        return {}
    ident = action.rsplit('.', 1)[-1]
    if is_safe_identifier(ident):
        return {'payment_provider': ident}
    return {}


def emit_logged_action(
    action: str,
    *,
    event_id: int | None = None,
    object_id: int | str | None = None,
    user_id: int | None = None,
    is_orga_action: bool = False,
    model: str | None = None,
    order_id: int | None = None,
    order_code: str | None = None,
    voucher_id: int | None = None,
    data: object = None,
) -> None:
    component = component_for_action(action)
    if not component:
        return
    safe_fields = safe_fields_from_log_data(data)
    for key, value in fields_from_action_name(action).items():
        safe_fields.setdefault(key, value)
    if order_code is not None:
        safe_fields.pop('order_code', None)
    elif 'order_code' in safe_fields:
        order_code = safe_fields.pop('order_code')
        if not isinstance(order_code, str):
            order_code = None
    log_event(component, action, outcome_for_action(action), event_id=event_id, object_id=object_id, user_id=user_id, is_orga_action=is_orga_action, model=model, order_id=order_id, order_code=order_code, voucher_id=voucher_id, **safe_fields)


_SKIP_REQUEST_LOG_PREFIXES: Final[tuple[str, ...]] = (
    '/static',
    '/media',
    '/jsi18n',
)


def log_request_start(request) -> None:
    path = getattr(request, 'path', '') or ''
    if any(path.startswith(prefix) for prefix in _SKIP_REQUEST_LOG_PREFIXES):
        return
    if path.rstrip('/') in ('/healthcheck', '/health', '/_health'):
        return
    match = getattr(request, 'resolver_match', None)
    route = getattr(match, 'view_name', None) if match else None
    log_event('core', 'request.start', OUTCOME_SUCCESS, route=route)


def log_request_outcome(request, response) -> None:
    path = getattr(request, 'path', '') or ''
    if any(path.startswith(prefix) for prefix in _SKIP_REQUEST_LOG_PREFIXES):
        return
    status = getattr(response, 'status_code', None)
    if not isinstance(status, int):
        return
    if path.rstrip('/') in ('/healthcheck', '/health', '/_health'):
        return
    started = getattr(request, '_operational_started', None)
    duration_ms = None
    if isinstance(started, (int, float)):
        duration_ms = int((time.monotonic() - started) * 1000)
    match = getattr(request, 'resolver_match', None)
    route = getattr(match, 'view_name', None) if match else None
    if status >= 500:
        action = 'request.error'
        error_code = 'server_error'
        outcome = OUTCOME_FAILURE
        level = logging.ERROR
    elif status == 401:
        action = 'auth.denied'
        error_code = 'unauthorized'
        outcome = OUTCOME_FAILURE
        level = logging.WARNING
    elif status == 403:
        action = 'permission.denied'
        error_code = 'forbidden'
        outcome = OUTCOME_FAILURE
        level = logging.WARNING
    else:
        action = 'request.end'
        error_code = None
        outcome = OUTCOME_SUCCESS if status < 400 else OUTCOME_FAILURE
        level = logging.INFO
    user = getattr(request, 'user', None)
    user_id = getattr(user, 'pk', None) if user is not None and getattr(user, 'is_authenticated', False) else None
    log_event('core', action, outcome, level=level, error_code=error_code, status=status, route=route, duration_ms=duration_ms, user_id=user_id)


def connect_operational_signals() -> None:
    global _signals_connected
    if _signals_connected:
        return
    _signals_connected = True

    from django.contrib.auth.signals import user_logged_in, user_login_failed

    def _on_login(sender, user, **kwargs):
        log_event('core', 'auth.login', OUTCOME_SUCCESS, user_id=getattr(user, 'pk', None))

    def _on_login_failed(sender, **kwargs):
        log_event('core', 'auth.login', OUTCOME_FAILURE, error_code='invalid_credentials')

    user_logged_in.connect(_on_login, dispatch_uid='eventyay.operational.user_logged_in')
    user_login_failed.connect(_on_login_failed, dispatch_uid='eventyay.operational.user_login_failed')


class OperationalLogFilter(logging.Filter):
    """Attach correlation IDs so existing logger calls pick them up."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if not getattr(record, 'request_id', None):
                record.request_id = get_request_id() or '-'
            if not getattr(record, 'job_id', None):
                record.job_id = get_job_id() or '-'
            if not getattr(record, 'component', None) and record.name.startswith('eventyay.'):
                record.component = record.name.split('.', 2)[1] if record.name.count('.') >= 1 else 'eventyay'
        except Exception:
            pass
        return True


class StructuredLogFormatter(logging.Formatter):
    """ISO-8601 UTC datetime plus allowlisted structured fields."""

    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return super().formatTime(record, datefmt or '%Y-%m-%dT%H:%M:%SZ')

    def format(self, record: logging.LogRecord) -> str:
        try:
            if not getattr(record, 'request_id', None):
                record.request_id = get_request_id() or '-'
            if not getattr(record, 'job_id', None):
                record.job_id = get_job_id() or '-'
            rendered = super().format(record)
            parts = [f'datetime={self.formatTime(record)}']
            for key in SAFE_LOG_FIELDS:
                value = getattr(record, key, None)
                if value is None or value == '' or value == '-':
                    continue
                parts.append(f'{key}={value}')
            return '%s %s' % (rendered, ' '.join(parts))
        except Exception:
            return logging.Formatter.format(self, record)


def production_log_formatter() -> StructuredLogFormatter:
    return StructuredLogFormatter(
        fmt='%(levelname)s %(asctime)s %(name)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%SZ',
    )
