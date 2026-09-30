import logging
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import RequestFactory
from django.http import HttpResponse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.middleware import CorrelationIdMiddleware
from eventyay.base.models import Event, Order, Organizer
from eventyay.base.models.audit import AuditLog
from eventyay.base.operational_logging import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    StructuredLogFormatter,
    bind_job_id,
    bind_request_id,
    component_for_action,
    emit_logged_action,
    is_tickets_action,
    log_event,
    outcome_for_action,
    production_log_formatter,
    reset_job_id,
    reset_request_id,
    safe_fields_from_log_data,
    sanitize_correlation_id,
)
from eventyay.base.payment import PaymentException
from eventyay.base.services.cart import CartError
from eventyay.base.services.checkin import CheckInError
from eventyay.base.services.orders import OrderError


@pytest.mark.parametrize(
    'action,expected',
    [
        ('eventyay.event.order.paid', OUTCOME_SUCCESS),
        ('eventyay.event.order.canceled', OUTCOME_SUCCESS),
        ('eventyay.event.order.refunded', OUTCOME_SUCCESS),
        ('eventyay.event.order.placed', OUTCOME_SUCCESS),
        ('eventyay.event.order.payment.failed', OUTCOME_FAILURE),
        ('eventyay.event.order.payment.canceled.failed', OUTCOME_FAILURE),
        ('eventyay.event.checkin.denied', OUTCOME_FAILURE),
        ('eventyay.event.checkin.unknown', OUTCOME_FAILURE),
        ('pretix.event.order.paid', OUTCOME_SUCCESS),
    ],
)
def test_outcome_for_action(action, expected):
    assert outcome_for_action(action) == expected


@pytest.mark.parametrize(
    'action,expected',
    [
        ('eventyay.event.order.paid', True),
        ('eventyay.voucher.redeemed', True),
        ('eventyay.event.quota.changed', True),
        ('eventyay.event.item.changed', True),
        ('eventyay.event.product.changed', True),
        ('eventyay.event.category.added', True),
        ('eventyay.event.question.changed', True),
        ('eventyay.subevent.quota.added', True),
        ('eventyay.giftcards.created', True),
        ('eventyay.control.views.checkin', True),
        ('eventyay.event.checkin', True),
        ('eventyay.waitinglist.voucher', True),
        ('eventyay.device.created', True),
        ('eventyay.device.revoked', True),
        ('eventyay.gate.deleted', True),
        ('eventyay.event.taxrule.changed', True),
        ('eventyay.event.tickets.settings', True),
        ('eventyay.seatingplan.changed', True),
        ('eventyay.plugins.ticketoutputpdf.layout.added', True),
        ('eventyay.plugins.badges.layout.changed', True),
        ('eventyay.event.payment.provider.stripe', True),
        ('eventyay.event.live.activated', True),
        ('eventyay.event.testmode.deactivated', True),
        ('eventyay.event.added', True),
        ('eventyay.event.changed', True),
        ('eventyay.event.deleted', True),
        ('eventyay.property.created', True),
        ('eventyay.device.updated', False),
        ('eventyay.event.plugins.enabled', False),
        ('eventyay.event.order.email.error', False),
        ('eventyay.event.order.email.custom_sent', False),
        ('eventyay.event.order.comment', False),
        ('eventyay.event.comment', False),
        ('eventyay.event.settings', False),
        ('eventyay.submission.create', False),
        ('eventyay.user.settings.changed', False),
        ('pretix.webhook.created', False),
        ('pretix.organizer.settings', False),
        ('eventyay.organizer.deleted', False),
        ('eventyay.control.auth.user.impersonated', False),
    ],
)
def test_is_tickets_action(action, expected):
    assert is_tickets_action(action) is expected


@pytest.mark.parametrize(
    'action,expected',
    [
        ('eventyay.event.order.paid', 'tickets'),
        ('eventyay.event.plugins.enabled', 'plugins'),
        ('eventyay.event.order.email.error', 'mail'),
        ('eventyay.mail.sent', 'mail'),
        ('eventyay.submission.create', 'talk'),
        ('eventyay.schedule.release', 'talk'),
        ('eventyay.submission.review.update', 'talk'),
        ('eventyay.cfp.update', 'talk'),
        ('eventyay.user.profile.update', 'talk'),
        ('eventyay.user.password.update', 'talk'),
        ('eventyay.user.token.create', 'talk'),
        ('eventyay.speaker_information.update', 'talk'),
        ('eventyay.room.changed', 'video'),
        ('pretix.webhook.created', 'plugins'),
        ('eventyay.control.auth.user.impersonated', 'core'),
        ('eventyay.eventyay_common.auth.login', 'core'),
        ('eventyay.team.created', 'core'),
        ('eventyay.invite.accepted', 'core'),
        ('eventyay.object.cloned', 'core'),
        ('eventyay.user.settings.2fa.enabled', 'core'),
        ('eventyay.user.settings.changed', 'core'),
        ('eventyay.user.oauth.authorized', 'core'),
        ('eventyay.event.meetup.created', 'tickets'),
        ('eventyay.speaker.imported', 'talk'),
        ('eventyay.event.settings.changed', 'tickets'),
        ('bbbserver.created', 'video'),
        ('event.created', 'video'),
        ('user.changed', 'core'),
        ('eventyay.event.action_required', None),
        ('eventyay.event.update', 'talk'),
        ('eventyay.event.talk_data.update', 'talk'),
        ('eventyay.organizer.follower_notification.sent', 'mail'),
        ('eventyay.organizer.deleted', 'core'),
        ('eventyay.user.settings.notifications.enabled', 'core'),
        ('pretix.organizer.settings', None),
        ('eventyay.submission.comment.create', 'talk'),
        ('eventyay.device.updated', None),
        ('eventyay.event.settings', None),
        ('eventyay.event.order.comment', None),
        ('auth.user.banned', 'video'),
        ('auth.user.deleted', 'video'),
        ('event.room.added', 'video'),
        ('event.tokens.generate', 'video'),
        ('chat.event.updated', None),
        ('auth.user.profile.changed', None),
    ],
)
def test_component_for_action(action, expected):
    assert component_for_action(action) is expected


def test_user_log_action_emits_without_payload(monkeypatch, caplog):
    from eventyay.base.models.auth import User

    caplog.set_level(logging.INFO, logger='eventyay.core')
    monkeypatch.setattr('eventyay.base.models.log.LogEntry.objects.create', lambda **kwargs: None)
    user = User(pk=7)
    user.log_action('eventyay.user.oauth.authorized', user=user, data={'application_name': 'secret-app'})
    assert any(getattr(rec, 'action', None) == 'eventyay.user.oauth.authorized' for rec in caplog.records)
    assert all('secret-app' not in rec.getMessage() for rec in caplog.records)


def test_audit_log_save_emits_without_payload(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger='eventyay.video')

    def fake_save(self, *args, **kwargs):
        self.pk = 1

    monkeypatch.setattr('django.db.models.base.Model.save', fake_save)
    AuditLog(event_id=3, user_id=9, type='auth.user.banned', data={'object': 'u1', 'reason': 'secret-reason'}).save()
    assert any(getattr(rec, 'action', None) == 'auth.user.banned' for rec in caplog.records)
    assert all('secret-reason' not in rec.getMessage() for rec in caplog.records)

    caplog.clear()
    AuditLog(event_id=3, user_id=9, type='chat.event.updated', data={'old': 'private chat text'}).save()
    assert not any(getattr(rec, 'action', None) == 'chat.event.updated' for rec in caplog.records)


def test_lock_timeout_and_shred_log_without_message(caplog):
    from eventyay.base.services.locking import LockTimeoutException
    from eventyay.base.shredder import ShredError

    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    LockTimeoutException()
    assert any(getattr(rec, 'action', None) == 'lock.timeout' for rec in caplog.records)

    caplog.clear()
    ShredError('The slug you entered was not correct.')
    assert any(getattr(rec, 'action', None) == 'shred.error' for rec in caplog.records)
    assert all('slug' not in rec.getMessage() for rec in caplog.records)


def test_upload_rejected_logs_error_code_only(caplog):
    from eventyay.storage.views import upload_rejected

    caplog.set_level(logging.WARNING, logger='eventyay.video')
    response = upload_rejected(type('E', (), {'pk': 12})(), 'file.type')
    assert response.status_code == 400
    assert any(getattr(rec, 'error_code', None) == 'file.type' for rec in caplog.records)


def test_lock_release_and_etherpad_config_log_without_message(caplog):
    from eventyay.base.services.etherpad import EtherpadConfigurationError
    from eventyay.base.services.locking import LockReleaseException

    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    LockReleaseException('Lock is not owned by this thread')
    assert any(getattr(rec, 'action', None) == 'lock.release' for rec in caplog.records)
    assert all('thread' not in rec.getMessage() for rec in caplog.records)

    caplog.clear()
    caplog.set_level(logging.WARNING, logger='eventyay.talk')
    EtherpadConfigurationError('No Etherpad instance URL is configured.')
    assert any(getattr(rec, 'error_code', None) == 'not_configured' for rec in caplog.records)
    assert all('URL' not in rec.getMessage() for rec in caplog.records)


def test_quota_exceeded_logs_without_detail(caplog):
    from eventyay.api.views.order import QuotaExceededAPIException

    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    QuotaExceededAPIException()
    assert any(getattr(rec, 'action', None) == 'quota.exceeded' for rec in caplog.records)


def test_geocode_address_logs_request_error(monkeypatch, caplog):
    import requests

    from eventyay.base.services import geo as geo_mod

    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    monkeypatch.setattr(geo_mod, 'clean_address_query', lambda q: 'x')
    monkeypatch.setattr(geo_mod, '_geocode_cache_key', lambda q: 'k')
    monkeypatch.setattr(geo_mod.cache, 'get', lambda key: None)
    monkeypatch.setattr(geo_mod, 'geocoding_is_available', lambda: True)
    monkeypatch.setattr(geo_mod, 'GlobalSettingsObject', lambda: type('GS', (), {'settings': None})())

    def boom(query, gs):
        raise requests.RequestException('upstream down')

    monkeypatch.setattr(geo_mod, '_geocode_with_configured_providers', boom)
    try:
        geo_mod.geocode_address('ignored')
    except requests.RequestException:
        pass
    assert any(getattr(rec, 'action', None) == 'connection.geocode' for rec in caplog.records)
    assert all('ignored' not in rec.getMessage() for rec in caplog.records)


def test_vat_connection_log_omits_vat_id_and_country(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    log_event(
        'tickets',
        'connection.vat',
        OUTCOME_FAILURE,
        error_code='vies_unavailable',
        backend='vies',
        vat_id='DE123456789',
        country='DE',
    )
    assert any(getattr(rec, 'action', None) == 'connection.vat' for rec in caplog.records)
    assert any(getattr(rec, 'backend', None) == 'vies' for rec in caplog.records)
    assert 'DE123456789' not in caplog.text
    assert not any(getattr(rec, 'vat_id', None) for rec in caplog.records)


def test_auth_2fa_failure_logs_user_id_only(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.core')
    log_event('core', 'auth.login', OUTCOME_FAILURE, error_code='2fa_failed', user_id=9, email='secret@example.com')
    rec = next(r for r in caplog.records if getattr(r, 'error_code', None) == '2fa_failed')
    assert rec.user_id == 9
    assert 'secret@example.com' not in caplog.text


def test_gmail_errors_log_without_message_text(caplog):
    from eventyay.base.gmail.errors import GmailRateLimitError

    caplog.set_level(logging.WARNING, logger='eventyay.mail')
    with pytest.raises(GmailRateLimitError):
        raise GmailRateLimitError('quota exceeded for user@example.com')
    rec = next(r for r in caplog.records if getattr(r, 'error_code', None) == 'gmail_rate_limit')
    assert rec.action == 'mail.send'
    assert 'user@example.com' not in rec.getMessage()


def test_sanitize_correlation_id_rejects_unsafe_values():
    generated = sanitize_correlation_id('not a valid id\nwith newline')
    assert generated != 'not a valid id\nwith newline'
    assert sanitize_correlation_id('abc-123_XYZ') == 'abc-123_XYZ'


def test_formatter_includes_datetime_and_allowlisted_fields_only():
    formatter = StructuredLogFormatter(fmt='%(levelname)s %(name)s: %(message)s')
    record = logging.LogRecord(
        name='eventyay.tickets',
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='tickets.eventyay.event.order.paid success',
        args=(),
        exc_info=None,
    )
    record.component = 'tickets'
    record.outcome = 'success'
    record.action = 'eventyay.event.order.paid'
    record.event_id = 7
    record.order_code = 'ABC12'
    record.email = 'buyer@example.test'
    record.card_number = '4242424242424242'
    line = formatter.format(record)
    assert 'datetime=' in line
    assert 'outcome=success' in line
    assert 'action=eventyay.event.order.paid' in line
    assert 'order_code=ABC12' in line
    assert 'buyer@example.test' not in line
    assert '4242424242424242' not in line
    assert 'email=' not in line


def test_correlation_middleware_sets_and_echoes_request_id():
    reset_request_id()
    factory = RequestFactory()
    captured = {}

    def get_response(request):
        from eventyay.base.operational_logging import get_request_id

        captured['rid'] = get_request_id()
        return HttpResponse('ok')

    middleware = CorrelationIdMiddleware(get_response)
    request = factory.get('/tickets/', HTTP_X_REQUEST_ID='corr-id-99')
    response = middleware(request)
    assert captured['rid'] == 'corr-id-99'
    assert response['X-Request-ID'] == 'corr-id-99'
    from eventyay.base.operational_logging import get_request_id

    assert get_request_id() is None


def test_correlation_middleware_logs_failures_and_request_end(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.core')
    factory = RequestFactory()
    middleware = CorrelationIdMiddleware(lambda request: HttpResponse('denied', status=403))
    middleware(factory.get('/control/orders/'))
    assert any(getattr(rec, 'action', None) == 'request.start' for rec in caplog.records)
    assert any(getattr(rec, 'action', None) == 'permission.denied' for rec in caplog.records)
    assert all('email' not in rec.getMessage() for rec in caplog.records)

    caplog.clear()
    middleware = CorrelationIdMiddleware(lambda request: HttpResponse('ok'))
    middleware(factory.get('/control/orders/'))
    assert any(getattr(rec, 'action', None) == 'request.start' for rec in caplog.records)
    assert any(getattr(rec, 'action', None) == 'request.end' and getattr(rec, 'status', None) == 200 for rec in caplog.records)


def test_correlation_middleware_is_first_in_stack():
    from django.conf import settings

    assert settings.MIDDLEWARE[0] == 'eventyay.base.middleware.CorrelationIdMiddleware'


def test_correlation_middleware_logs_server_errors(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.core')
    factory = RequestFactory()
    middleware = CorrelationIdMiddleware(lambda request: HttpResponse('busy', status=503))
    middleware(factory.get('/control/orders/'))
    assert any(getattr(rec, 'action', None) == 'request.error' and getattr(rec, 'status', None) == 503 for rec in caplog.records)


def test_healthcheck_failure_does_not_emit_request_error(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.core')
    factory = RequestFactory()
    middleware = CorrelationIdMiddleware(lambda request: HttpResponse('Database not available.', status=503))
    middleware(factory.get('/healthcheck/'))
    actions = [getattr(rec, 'action', None) for rec in caplog.records]
    assert 'request.start' not in actions
    assert 'request.error' not in actions
    assert 'request.end' not in actions


def test_send_mail_exception_already_logged_does_not_duplicate(caplog):
    from eventyay.base.services.mail import SendMailException

    caplog.set_level(logging.INFO, logger='eventyay.mail')
    log_event('mail', 'mail.bounce', OUTCOME_FAILURE, error_code='recipient_refused', smtp_code=550)
    with pytest.raises(SendMailException):
        raise SendMailException('Failed to send', already_logged=True)
    send_failed = [
        rec for rec in caplog.records
        if getattr(rec, 'action', None) == 'mail.send' and getattr(rec, 'error_code', None) == 'send_failed'
    ]
    assert send_failed == []
    assert any(getattr(rec, 'action', None) == 'mail.bounce' for rec in caplog.records)


def test_log_event_scrubs_unsafe_error_code(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.mail')
    log_event('mail', 'mail.send', OUTCOME_FAILURE, error_code='Failed for user@example.com')
    rec = next(r for r in caplog.records if getattr(r, 'action', None) == 'mail.send')
    assert rec.error_code == 'invalid'
    assert 'user@example.com' not in caplog.text


def test_cart_error_logs_failure_without_payload(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    with pytest.raises(CartError):
        raise CartError('unavailable')
    assert any('cart.error' in rec.message and rec.outcome == 'failure' for rec in caplog.records)
    assert all('secret' not in rec.getMessage() for rec in caplog.records)


def test_order_error_logs_failure(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    with pytest.raises(OrderError):
        raise OrderError('unavailable')
    assert any(getattr(rec, 'action', None) == 'order.error' for rec in caplog.records)


def test_payment_exception_does_not_log_provider_text(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    secret_text = 'tok_live_SUPERSECRET card 4242 buyer@example.test'
    with pytest.raises(PaymentException):
        raise PaymentException(secret_text)
    text = caplog.text
    assert 'payment.exception' in text
    assert secret_text not in text
    assert 'tok_live_SUPERSECRET' not in text
    assert 'buyer@example.test' not in text


def test_checkin_error_logs_code_not_message(caplog):
    caplog.set_level(logging.WARNING, logger='eventyay.tickets')
    with pytest.raises(CheckInError):
        raise CheckInError('Already redeemed by Jane Doe jane@example.test', 'already_redeemed')
    assert any(getattr(rec, 'error_code', None) == 'already_redeemed' for rec in caplog.records)
    assert 'jane@example.test' not in caplog.text
    assert 'Jane Doe' not in caplog.text


@pytest.mark.django_db
def test_log_action_emits_structured_success_without_payload(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.tickets')
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy-log')
        event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy-log', date_from=now())
        order = Order.objects.create(
            code='LOG1A',
            event=event,
            email='hidden@example.test',
            status=Order.STATUS_PENDING,
            locale='en',
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('10.00'),
        )
    with scopes_disabled():
        order.log_action(
            'eventyay.event.order.paid',
            data={'email': 'hidden@example.test', 'secret': 'shh', 'name': 'Ada Lovelace'},
        )
    text = caplog.text
    assert 'eventyay.event.order.paid' in text
    assert 'outcome=success' in text or any(getattr(rec, 'outcome', None) == 'success' for rec in caplog.records)
    assert 'LOG1A' in text or any(getattr(rec, 'order_code', None) == 'LOG1A' for rec in caplog.records)
    assert 'hidden@example.test' not in text
    assert 'Ada Lovelace' not in text
    assert 'shh' not in text


@pytest.mark.django_db
def test_log_action_failure_marker(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.tickets')
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy-log2')
        event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy-log2', date_from=now())
        order = Order.objects.create(
            code='LOG2B',
            event=event,
            status=Order.STATUS_PENDING,
            locale='en',
            datetime=now(),
            expires=now() + timedelta(days=10),
            total=Decimal('10.00'),
        )
    with scopes_disabled():
        order.log_action('eventyay.event.order.payment.failed', data={'info': 'raw provider body'})
    assert any(
        getattr(rec, 'outcome', None) == 'failure' and 'payment.failed' in getattr(rec, 'action', '')
        for rec in caplog.records
    )
    assert 'raw provider body' not in caplog.text


def test_emit_logged_action_ignores_non_ticket_actions(caplog):
    caplog.set_level(logging.INFO)
    emit_logged_action('pretix.organizer.settings', event_id=1)
    emit_logged_action('eventyay.event.settings', event_id=1)
    assert caplog.records == []


def test_bind_request_id_appears_on_ticket_log(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.tickets')
    bind_request_id('fixed-request-id')
    try:
        emit_logged_action('eventyay.event.order.placed', event_id=1, order_code='ZZZ')
    finally:
        reset_request_id()
    assert any(getattr(rec, 'request_id', None) == 'fixed-request-id' for rec in caplog.records)


def test_safe_fields_from_log_data_keeps_provider_drops_payloads():
    fields = safe_fields_from_log_data(
        {
            'provider': 'stripe',
            'payment': 88,
            'local_id': 2,
            'info': 'tok_live_secret buyer@example.test',
            'email': 'buyer@example.test',
            'error': 'Card declined for Jane Doe',
        }
    )
    assert fields == {
        'payment_provider': 'stripe',
        'payment_id': 88,
        'payment_local_id': 2,
    }


def _formatted_tickets_logs(caplog):
    formatter = production_log_formatter()
    return [formatter.format(record) for record in caplog.records]


def test_rendered_log_examples_cover_ticket_flows(caplog):
    caplog.set_level(logging.INFO)
    bind_request_id('req-7f3a9c')
    bind_job_id('c0ffee12-task')
    try:
        emit_logged_action(
            'eventyay.event.order.placed',
            event_id=12,
            order_id=34,
            order_code='ABC12',
            object_id=34,
            model='Order',
        )
        emit_logged_action(
            'eventyay.event.order.paid',
            event_id=12,
            order_id=34,
            order_code='ABC12',
            object_id=34,
            model='Order',
        )
        emit_logged_action(
            'eventyay.event.order.payment.started',
            event_id=12,
            order_id=34,
            order_code='ABC12',
            data={'provider': 'stripe', 'payment': 88, 'local_id': 2, 'info': 'secret-token'},
        )
        emit_logged_action(
            'eventyay.event.order.payment.failed',
            event_id=12,
            order_id=34,
            order_code='ABC12',
            data={'provider': 'stripe', 'info': 'card_error buyer@example.test'},
        )
        emit_logged_action(
            'eventyay.event.order.canceled',
            event_id=12,
            order_id=34,
            order_code='ABC12',
            is_orga_action=True,
            user_id=9,
        )
        emit_logged_action(
            'eventyay.event.order.refunded',
            event_id=12,
            order_id=34,
            order_code='ABC12',
        )
        emit_logged_action(
            'eventyay.event.checkin',
            event_id=12,
            order_code='ABC12',
            data={'list': 5, 'position': 77},
        )
        emit_logged_action('eventyay.voucher.redeemed', event_id=12, voucher_id=4, order_code=None)
        emit_logged_action('eventyay.event.quota.closed', event_id=12, object_id=3, model='Quota')
        emit_logged_action('eventyay.waitinglist.voucher', event_id=12, voucher_id=4)
        emit_logged_action('eventyay.device.revoked', object_id=1, is_orga_action=True)
        emit_logged_action('eventyay.gate.created', object_id=2, is_orga_action=True)
        emit_logged_action('eventyay.plugins.ticketoutputpdf.layout.changed', event_id=12, is_orga_action=True)
        emit_logged_action('eventyay.plugins.badges.layout.added', event_id=12, is_orga_action=True)
        emit_logged_action(
            'eventyay.event.payment.provider.stripe',
            event_id=12,
            is_orga_action=True,
            data={'secret_key': 'sk_live_not_logged'},
        )
        emit_logged_action('eventyay.event.plugins.enabled', event_id=12, is_orga_action=True)
        emit_logged_action('eventyay.event.live.activated', event_id=12, is_orga_action=True)
        emit_logged_action('eventyay.event.settings', event_id=12, is_orga_action=True)
        emit_logged_action('eventyay.event.comment', event_id=12, is_orga_action=True)
        emit_logged_action('eventyay.event.order.email.error', event_id=12, order_code='ABC12')
        emit_logged_action('eventyay.device.updated', object_id=1)
        emit_logged_action('eventyay.submission.create', event_id=12, object_id=99)
        emit_logged_action('eventyay.schedule.release', event_id=12, object_id=3)
        emit_logged_action('eventyay.room.changed', event_id=12, object_id=4)
        emit_logged_action('pretix.webhook.created', object_id=8, is_orga_action=True)
        log_event('mail', 'mail.send', OUTCOME_SUCCESS, event_id=12, mail_type='order')
        log_event('tickets', 'cart.error', OUTCOME_FAILURE, error_code='cart_error', event_id=12)
        log_event('tickets', 'checkout.cart_invalid', OUTCOME_FAILURE, error_code='cart_invalid', event_id=12)
        log_event(
            'tickets',
            'payment.handoff',
            OUTCOME_SUCCESS,
            event_id=12,
            payment_provider='stripe',
        )
        log_event('tickets', 'checkin.error', OUTCOME_FAILURE, error_code='already_redeemed', event_id=12)
        log_event('tickets', 'voucher.apply', OUTCOME_SUCCESS, event_id=12)
    finally:
        reset_request_id()
        reset_job_id()

    lines = _formatted_tickets_logs(caplog)
    joined = '\n'.join(lines)
    assert 'secret-token' not in joined
    assert 'buyer@example.test' not in joined
    assert any('action=eventyay.event.order.placed' in line and 'outcome=success' in line for line in lines)
    assert any('action=eventyay.event.order.payment.started' in line and 'payment_provider=stripe' in line for line in lines)
    assert any('action=eventyay.event.order.payment.failed' in line and 'outcome=failure' in line for line in lines)
    assert any('datetime=' in line and 'request_id=req-7f3a9c' in line and 'job_id=c0ffee12-task' in line for line in lines)
    assert any('action=eventyay.event.checkin' in line and 'checkin_list_id=5' in line for line in lines)
    assert any('action=payment.handoff' in line and 'outcome=success' in line for line in lines)
    assert any('error_code=already_redeemed' in line for line in lines)
    assert any('action=voucher.apply' in line and 'outcome=success' in line for line in lines)
    assert any('action=eventyay.waitinglist.voucher' in line for line in lines)
    assert any('action=eventyay.device.revoked' in line for line in lines)
    assert any('action=eventyay.gate.created' in line for line in lines)
    assert any('action=eventyay.plugins.ticketoutputpdf.layout.changed' in line for line in lines)
    assert any('action=eventyay.plugins.badges.layout.added' in line for line in lines)
    assert any(
        'action=eventyay.event.payment.provider.stripe' in line and 'payment_provider=stripe' in line for line in lines
    )
    assert any('action=eventyay.event.plugins.enabled' in line and 'component=plugins' in line for line in lines)
    assert any('action=eventyay.event.live.activated' in line for line in lines)
    assert any('action=eventyay.event.order.email.error' in line and 'component=mail' in line for line in lines)
    assert any('action=eventyay.submission.create' in line and 'component=talk' in line for line in lines)
    assert any('action=eventyay.schedule.release' in line and 'component=talk' in line for line in lines)
    assert any('action=eventyay.room.changed' in line and 'component=video' in line for line in lines)
    assert any('action=pretix.webhook.created' in line and 'component=plugins' in line for line in lines)
    assert any('action=mail.send' in line and 'component=mail' in line for line in lines)
    assert 'sk_live_not_logged' not in joined
    assert 'event.settings' not in joined
    assert 'event.comment' not in joined
    assert 'device.updated' not in joined


def test_send_mail_exception_does_not_log_recipient(caplog):
    from eventyay.common.exceptions import SendMailException

    caplog.set_level(logging.WARNING, logger='eventyay.mail')
    with pytest.raises(SendMailException):
        raise SendMailException('Failed to send an email to buyer@example.test')
    assert any(getattr(rec, 'action', None) == 'mail.send' for rec in caplog.records)
    assert 'buyer@example.test' not in caplog.text


def test_janus_error_does_not_log_server_url(caplog):
    from eventyay.base.services.janus import JanusError

    caplog.set_level(logging.WARNING, logger='eventyay.video')
    with pytest.raises(JanusError):
        raise JanusError('Could not connect to Janus server wss://janus.example/ws?secret=abc')
    assert any(getattr(rec, 'action', None) == 'janus.connection' for rec in caplog.records)
    assert 'secret=abc' not in caplog.text
    assert 'janus.example' not in caplog.text


def test_consumer_exception_logs_code_not_message(caplog):
    from eventyay.features.live.exceptions import ConsumerException

    caplog.set_level(logging.WARNING, logger='eventyay.video')
    with pytest.raises(ConsumerException):
        raise ConsumerException('bbb.failed', 'Jane Doe could not join')
    assert any(getattr(rec, 'error_code', None) == 'bbb.failed' for rec in caplog.records)
    assert 'Jane Doe' not in caplog.text


def test_log_event_omits_urls_and_secrets_on_connections(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.video')
    log_event(
        'video',
        'connection.get',
        OUTCOME_FAILURE,
        error_code='http_error',
        status=502,
        duration_ms=41,
        event_id=12,
        backend='bbb',
    )
    log_event(
        'video',
        'connection.websocket',
        OUTCOME_FAILURE,
        error_code='janus_error',
        backend='wss://janus.example/ws?secret=abc',
    )
    assert any(getattr(rec, 'backend', None) == 'bbb' and getattr(rec, 'action', None) == 'connection.get' for rec in caplog.records)
    assert any(getattr(rec, 'backend', None) == 'unknown' for rec in caplog.records)
    assert 'janus.example' not in caplog.text
    assert 'secret=abc' not in caplog.text


def test_bbb_server_unavailable_logs_without_event_name(caplog):
    from eventyay.base.services.bbb import BBBServerUnavailable

    caplog.set_level(logging.WARNING, logger='eventyay.video')
    with pytest.raises(BBBServerUnavailable):
        raise BBBServerUnavailable('No active BBB server available for event SecretConf (room=1).')
    assert any(getattr(rec, 'action', None) == 'connection.choose_server' for rec in caplog.records)
    assert 'SecretConf' not in caplog.text


def test_log_event_does_not_raise_when_logger_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('handler exploded')

    monkeypatch.setattr(logging.Logger, 'log', boom)
    log_event('tickets', 'probe', OUTCOME_SUCCESS, event_id=1)


def test_client_log_allowlist_accepts_frontend_actions():
    from eventyay.features.live.modules.event import CLIENT_LOG_ACTIONS

    assert 'bbb.recordings' in CLIENT_LOG_ACTIONS
    assert 'interpretation.config' in CLIENT_LOG_ACTIONS
    assert 'stream.schedule' in CLIENT_LOG_ACTIONS
    assert 'upload' in CLIENT_LOG_ACTIONS


def test_mail_bounce_and_enqueue_actions_are_structured(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.mail')
    log_event('mail', 'mail.enqueue', OUTCOME_SUCCESS, object_id=9, mail_type='submission.new')
    log_event('mail', 'mail.bounce', OUTCOME_FAILURE, error_code='recipient_refused', smtp_code=550)
    log_event('mail', 'mail.complaint', OUTCOME_FAILURE, error_code='policy_rejected', smtp_code=554)
    assert any(getattr(rec, 'action', None) == 'mail.enqueue' for rec in caplog.records)
    assert any(getattr(rec, 'action', None) == 'mail.bounce' and getattr(rec, 'smtp_code', None) == 550 for rec in caplog.records)
    assert any(getattr(rec, 'action', None) == 'mail.complaint' and getattr(rec, 'smtp_code', None) == 554 for rec in caplog.records)
    assert all('@' not in rec.getMessage() for rec in caplog.records)


def test_job_lifecycle_and_config_loaded_are_structured(caplog):
    caplog.set_level(logging.INFO, logger='eventyay.core')
    log_event('core', 'job.enqueue', OUTCOME_SUCCESS, job_name='eventyay.mail.send', job_id='abc')
    log_event('core', 'job.start', OUTCOME_SUCCESS, job_name='eventyay.mail.send', job_id='abc')
    log_event('core', 'job.finish', OUTCOME_SUCCESS, job_name='eventyay.mail.send', job_id='abc', job_state='SUCCESS')
    log_event('core', 'job.retry', OUTCOME_FAILURE, error_code='retry', job_name='eventyay.mail.send', job_id='abc')
    log_event('core', 'config.loaded', OUTCOME_SUCCESS)
    assert {getattr(rec, 'action', None) for rec in caplog.records} >= {'job.enqueue', 'job.start', 'job.finish', 'job.retry', 'config.loaded'}


def test_correlation_middleware_returns_response_if_logging_fails(monkeypatch):
    reset_request_id()
    factory = RequestFactory()

    def boom(*args, **kwargs):
        raise RuntimeError('log fail')

    monkeypatch.setattr('eventyay.base.operational_logging.log_request_outcome', boom)
    middleware = CorrelationIdMiddleware(lambda request: HttpResponse('ok'))
    response = middleware(factory.get('/tickets/'))
    assert response.status_code == 200
    from eventyay.base.operational_logging import get_request_id

    assert get_request_id() is None


def test_payment_exception_still_carries_user_facing_message():
    with pytest.raises(PaymentException, match='Payment was declined'):
        raise PaymentException('Payment was declined')
