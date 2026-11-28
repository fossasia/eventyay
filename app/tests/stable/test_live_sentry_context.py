import asyncio
import importlib
import json
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sentry_sdk
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings as django_settings
from django.core.exceptions import PermissionDenied
from django.core.handlers.wsgi import WSGIHandler
from django.db import connection
from django.http import Http404
from django.test import RequestFactory
from requests import RequestException
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration, DjangoRequestExtractor
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from eventyay.base.models import User
from eventyay.celery_app import app as celery_app
from eventyay.config import sentry as sentry_config
from eventyay.config.asgi import PatchedSentryAsgiMiddleware
from eventyay.features.live import routing
from eventyay.features.live.consumers import MainConsumer
from eventyay.features.live.modules.auth import AuthModule
from eventyay.features.live.modules.chat import ChatModule
from eventyay.features.live.modules.room import RoomModule
from eventyay.features.live.tasks import send_chat_webhook


class CollectingTransport(Transport):
    """In-memory Sentry transport for local test assertions."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.item_types = []
        self.log_payloads = []

    def capture_envelope(self, envelope):
        for item in envelope:
            self.item_types.append(item.type)
            if item.type == 'log':
                payload = item.payload.json
                if payload is None:
                    payload = json.loads(item.get_bytes().decode('utf-8'))
                self.log_payloads.append(payload)

        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


@asynccontextmanager
async def _noop_statsd():
    yield MagicMock()


@asynccontextmanager
async def _broken_redis():
    raise RuntimeError('redis unavailable')
    yield


@pytest.fixture
def sentry_transport():
    transport = CollectingTransport()
    previous_client = sentry_sdk.get_client()
    sentry_sdk.init(
        dsn='https://public@sentry.example.com/1',
        transport=transport,
        data_collection=django_settings.SENTRY_DATA_COLLECTION,
        default_integrations=False,
        auto_enabling_integrations=False,
    )
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(previous_client)


@pytest.fixture
def sentry_integrations_transport():
    transport = CollectingTransport()
    previous_client = sentry_sdk.get_client()
    sentry_sdk.init(
        dsn='https://public@sentry.example.com/1',
        transport=transport,
        integrations=[
            CeleryIntegration(),
            DjangoIntegration(),
            LoggingIntegration(level=None, event_level=logging.ERROR),
        ],
        data_collection=django_settings.SENTRY_DATA_COLLECTION,
    )
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(previous_client)


@pytest.fixture
def in_memory_channel_layer(settings):
    settings.CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
    settings.REDIS_USE_PUBSUB = False
    settings.SENTRY_DSN = 'https://public@sentry.example.com/1'


@pytest.mark.asyncio
async def test_concurrent_connections_keep_their_own_event_context(sentry_transport, in_memory_channel_layer):
    events = {'first': MagicMock(id=101, pk=101), 'second': MagicMock(id=202, pk=202)}

    async def ping(last_ping, user):
        try:
            raise RuntimeError(f'ping-check-{last_ping}')
        except RuntimeError as exc:
            sentry_sdk.capture_exception(exc)
        return last_ping

    application = PatchedSentryAsgiMiddleware(URLRouter(routing.websocket_urlpatterns))

    with (
        patch('eventyay.features.live.consumers.get_event', side_effect=lambda event_id: events[event_id]),
        patch('eventyay.features.live.consumers.register_connection', new=AsyncMock()),
        patch('eventyay.features.live.consumers.ping_connection', side_effect=ping),
        patch('eventyay.features.live.consumers.statsd', _noop_statsd),
        patch('eventyay.features.live.consumers.log_event'),
        patch.object(MainConsumer, 'disconnect', new=AsyncMock()),
    ):
        first = WebsocketCommunicator(application, '/ws/event/first/')
        second = WebsocketCommunicator(application, '/ws/event/second/')
        connected = await asyncio.gather(first.connect(), second.connect())
        assert [result[0] for result in connected] == [True, True]

        for communicator in (first, second, first):
            await communicator.send_json_to(['ping', 1])
            assert await communicator.receive_json_from() == ['pong', 1]

        await first.disconnect()
        await second.disconnect()

    sentry_sdk.flush()
    assert [event['extra']['event'] for event in sentry_transport.events] == [101, 202, 101]
    assert all(event['request']['method'] == 'WEBSOCKET' for event in sentry_transport.events)
    assert all(event['exception']['values'][-1]['type'] == 'RuntimeError' for event in sentry_transport.events)


@pytest.mark.asyncio
async def test_concurrent_logins_report_exceptions_with_their_own_user(sentry_transport, settings):
    settings.SENTRY_DSN = 'https://public@sentry.example.com/1'
    both_logged_in = asyncio.Barrier(2)

    def login(client_id, **kwargs):
        user_id = int(client_id.removeprefix('client-'))
        return MagicMock(user=MagicMock(id=user_id, type=User.UserType.PERSON), view=None)

    async def login_and_report(user_id):
        consumer = MagicMock()
        consumer.scope = {'query_string': b''}
        consumer.event.config = {}
        module = AuthModule(consumer)
        with sentry_sdk.isolation_scope():
            with pytest.raises(RuntimeError) as excinfo:
                await module.login({'client_id': f'client-{user_id}'})
            await both_logged_in.wait()
            sentry_sdk.capture_exception(excinfo.value)

    with (
        patch('eventyay.features.live.modules.auth.login', side_effect=login),
        patch('eventyay.features.live.modules.auth.aredis', _broken_redis),
    ):
        await asyncio.gather(login_and_report(11), login_and_report(22))

    sentry_sdk.flush()
    reported = sorted(
        (event['user']['id'], event['exception']['values'][-1]['type']) for event in sentry_transport.events
    )
    assert reported == [('11', 'RuntimeError'), ('22', 'RuntimeError')]


@pytest.mark.asyncio
async def test_concurrent_room_entries_keep_their_own_room(sentry_transport, settings):
    settings.SENTRY_DSN = 'https://public@sentry.example.com/1'
    both_entered = asyncio.Barrier(2)
    enter_room = RoomModule.enter_room.__wrapped__.__wrapped__

    def make_module(room_id):
        consumer = MagicMock()
        consumer.event.config = {}
        consumer.event.has_permission_async = AsyncMock(return_value=False)
        consumer.channel_layer.group_add = AsyncMock()
        consumer.send_success = AsyncMock()
        module = RoomModule(consumer)
        module.room = MagicMock(pk=room_id)
        module.room.name = f'Room {room_id}'
        return module

    async def enter_and_report(room_id):
        module = make_module(room_id)
        with sentry_sdk.isolation_scope():
            await enter_room(module, {'room': room_id})
            await both_entered.wait()
            try:
                raise RuntimeError('after room enter')
            except RuntimeError as exc:
                sentry_sdk.capture_exception(exc)

    room_module = 'eventyay.features.live.modules.room'
    with (
        patch(f'{room_module}.is_room_visible_for_attendee_async', new=AsyncMock(return_value=True)),
        patch(f'{room_module}.start_view', new=AsyncMock(return_value=(MagicMock(), 1))),
        patch(f'{room_module}.get_channel_layer', return_value=MagicMock(group_send=AsyncMock())),
        patch.object(RoomModule, '_update_view_count', new=AsyncMock()),
    ):
        await asyncio.gather(enter_and_report(1), enter_and_report(2))

    sentry_sdk.flush()
    rooms = sorted(event['extra']['last_room'] for event in sentry_transport.events)
    assert rooms == ['1', '2']
    assert all(event['breadcrumbs']['values'][-1]['category'] == 'room' for event in sentry_transport.events)
    assert all(event['exception']['values'][-1]['type'] == 'RuntimeError' for event in sentry_transport.events)


@pytest.mark.asyncio
async def test_concurrent_chat_commands_keep_their_own_channel(sentry_transport):
    both_dispatched = asyncio.Barrier(2)

    async def dispatch(content):
        await both_dispatched.wait()
        raise RuntimeError(f'chat failure {content[2].get("channel")}')

    async def dispatch_and_report(channel_id):
        module = ChatModule(MagicMock())
        with sentry_sdk.isolation_scope():
            with pytest.raises(RuntimeError) as excinfo:
                await module.dispatch_command(['chat.join', 1, {'channel': channel_id}])
            sentry_sdk.capture_exception(excinfo.value)

    with patch('eventyay.features.live.modules.base.BaseModule.dispatch_command', side_effect=dispatch):
        await asyncio.gather(dispatch_and_report('abc'), dispatch_and_report('def'))

    sentry_sdk.flush()
    channels = sorted(event['extra']['last_channel'] for event in sentry_transport.events)
    assert channels == ['abc', 'def']
    assert all(event['exception']['values'][-1]['type'] == 'RuntimeError' for event in sentry_transport.events)


def test_request_body_and_cookies_are_not_collected(sentry_transport):
    request = RequestFactory().post(
        '/control/login',
        data={'email': 'ada@example.com', 'password': 'hunter2'},
        HTTP_COOKIE='sessionid=xyz',
    )
    event = {}
    DjangoRequestExtractor(request).extract_into_event(event)

    assert 'data' not in event['request']
    assert 'cookies' not in event['request']


def _failing_header_view(_request):
    raise RuntimeError('header check failure')


def test_sensitive_request_headers_are_filtered(sentry_integrations_transport):
    environ = (
        RequestFactory()
        .get(
            '/sentry-header-test/',
            HTTP_AUTHORIZATION='Token abc123',
            HTTP_COOKIE='sessionid=xyz',
            HTTP_X_CSRFTOKEN='csrf-secret-value',
            HTTP_X_FORWARDED_FOR='203.0.113.7',
            HTTP_X_REAL_IP='203.0.113.8',
            HTTP_FORWARDED='for=203.0.113.9;proto=https',
            HTTP_USER_AGENT='Mozilla/5.0',
        )
        .environ
    )
    with (
        patch('django.core.handlers.wsgi.signals.request_started.send'),
        patch.object(WSGIHandler, 'load_middleware'),
        patch.object(WSGIHandler, 'get_response', side_effect=_failing_header_view),
        pytest.raises(RuntimeError, match='header check failure'),
    ):
        WSGIHandler()(environ, lambda _status, _headers: None)

    sentry_sdk.flush()
    assert len(sentry_integrations_transport.events) == 1
    event = sentry_integrations_transport.events[0]
    headers = event['request']['headers']
    serialized_request = json.dumps(event['request'])

    for sensitive_header in (
        'Authorization',
        'Cookie',
        'X-Csrftoken',
        'X-Forwarded-For',
        'X-Real-Ip',
        'Forwarded',
    ):
        matched_key = next((k for k in headers if k.lower() == sensitive_header.lower()), None)
        assert matched_key is not None
        assert headers[matched_key] == '[Filtered]'

    for secret_value in (
        'Token abc123',
        'sessionid=xyz',
        'csrf-secret-value',
        '203.0.113.7',
        '203.0.113.8',
        'for=203.0.113.9;proto=https',
    ):
        assert secret_value not in serialized_request

    assert headers['User-Agent'] == 'Mozilla/5.0'


def test_celery_task_payload_is_not_collected(sentry_integrations_transport):
    recipient = '@'.join(('private-recipient', 'example.invalid'))
    body_text = ' '.join(('confidential', 'message', 'body'))
    subject_text = ' '.join(('private', 'subject'))

    @celery_app.task(name='tests.sentry.failing_notification_task')
    def failing_notification_task(recipient_email, message_body, subject=None):
        raise RuntimeError('delivery failed')

    result = failing_notification_task.apply(
        args=(recipient, body_text),
        kwargs={'subject': subject_text},
    )
    assert result.failed()

    sentry_sdk.flush()
    celery_events = [event for event in sentry_integrations_transport.events if 'celery-job' in event.get('extra', {})]
    assert len(celery_events) == 1
    event = celery_events[0]

    celery_job = event['extra']['celery-job']
    assert celery_job == {'task_name': 'tests.sentry.failing_notification_task'}
    assert 'args' not in celery_job
    assert 'kwargs' not in celery_job

    serialized_extra = json.dumps(event['extra'])
    assert recipient not in serialized_extra
    assert body_text not in serialized_extra
    assert subject_text not in serialized_extra

    assert event['tags']['celery_task_id']
    assert event['exception']['values'][-1]['type'] == 'RuntimeError'


def _execute_sensitive_query():
    with connection.cursor() as cursor:
        cursor.execute('SELECT %s', ['@'.join(('private-test-email', 'example.invalid'))])


@pytest.mark.django_db
def test_database_query_parameters_are_not_collected(sentry_integrations_transport):
    _execute_sensitive_query()

    try:
        raise RuntimeError('after database query')
    except RuntimeError as exc:
        sentry_sdk.capture_exception(exc)

    sentry_sdk.flush()
    assert len(sentry_integrations_transport.events) == 1
    event = sentry_integrations_transport.events[0]

    query_breadcrumbs = [
        crumb for crumb in event.get('breadcrumbs', {}).get('values', []) if crumb.get('category') == 'query'
    ]
    assert query_breadcrumbs
    assert any('SELECT' in (crumb.get('message') or '') for crumb in query_breadcrumbs)
    assert all('db.params' not in (crumb.get('data') or {}) for crumb in query_breadcrumbs)
    assert '@'.join(('private-test-email', 'example.invalid')) not in json.dumps(event)


def test_handled_logging_exception_is_captured(sentry_integrations_transport):
    with (
        patch('eventyay.features.live.tasks.post_webhook', side_effect=RequestException('webhook timeout')),
        patch('eventyay.features.live.tasks.log_event'),
    ):
        result = send_chat_webhook.run(
            {'event': 'chat.message'},
            'https://example.invalid/webhook',
            'test-hmac-secret',
        )

    assert result is None
    sentry_sdk.flush()
    assert len(sentry_integrations_transport.events) == 1
    assert sentry_integrations_transport.item_types == ['event']
    assert sentry_integrations_transport.log_payloads == []
    event = sentry_integrations_transport.events[0]
    assert event['level'] == 'error'
    assert event['logger'] == 'eventyay.features.live.tasks'
    assert event['exception']['values'][-1]['type'] == 'RequestException'


def test_info_logs_do_not_send_sentry_log_envelopes(sentry_integrations_transport):
    marker = 'operation=processing'
    logger = logging.getLogger('eventyay.tests.sentry_logging')
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        logger.info('Processing request (%s)', marker)
        sentry_sdk.flush()

        assert sentry_integrations_transport.events == []
        assert 'log' not in sentry_integrations_transport.item_types
        assert sentry_integrations_transport.log_payloads == []

        try:
            raise RuntimeError('downstream error after info log')
        except RuntimeError:
            logger.error('Handled error after info log', exc_info=True)
    finally:
        logger.setLevel(previous_level)

    sentry_sdk.flush()
    assert len(sentry_integrations_transport.events) == 1
    assert sentry_integrations_transport.item_types == ['event']
    assert sentry_integrations_transport.log_payloads == []

    event = sentry_integrations_transport.events[0]
    assert event['level'] == 'error'
    assert event['logger'] == 'eventyay.tests.sentry_logging'
    assert event['exception']['values'][-1]['type'] == 'RuntimeError'

    breadcrumbs = event.get('breadcrumbs', {}).get('values', [])
    info_crumbs = [
        crumb
        for crumb in breadcrumbs
        if crumb.get('category') == 'eventyay.tests.sentry_logging' and crumb.get('level') == 'info'
    ]
    assert len(info_crumbs) == 1
    assert marker in info_crumbs[0]['message']


def test_sensitive_frame_variables_are_filtered(sentry_transport):
    def save_token(token, password, secret, api_key, order_code):
        raise RuntimeError(f'could not save {order_code}')

    try:
        save_token('eyJhbGciOiJIUzI1NiJ9.payload.signature', 'hunter2', 's3cr3t', 'sk_test_123', 'ABC12')
    except RuntimeError as exc:
        sentry_sdk.capture_exception(exc)

    sentry_sdk.flush()
    frame = sentry_transport.events[-1]['exception']['values'][-1]['stacktrace']['frames'][-1]
    assert 'vars' not in frame


def _raise_with_sensitive_locals(env_val, arg_val, kwarg_val):
    environ = {'HTTP_AUTHORIZATION': env_val}
    args = (arg_val,)
    kwargs = {'message_body': kwarg_val}
    assert environ and args and kwargs
    raise RuntimeError('stack frame check failure')


def test_stack_frame_local_variables_are_not_collected(sentry_integrations_transport):
    secret_env = '-'.join(('env', 'secret', '991'))
    secret_arg = '-'.join(('arg', 'secret', '992'))
    secret_kwarg = '-'.join(('kwarg', 'secret', '993'))

    try:
        _raise_with_sensitive_locals(secret_env, secret_arg, secret_kwarg)
    except RuntimeError as exc:
        sentry_sdk.capture_exception(exc)

    sentry_sdk.flush()
    assert len(sentry_integrations_transport.events) == 1
    event = sentry_integrations_transport.events[0]
    serialized = json.dumps(event)

    assert secret_env not in serialized
    assert secret_arg not in serialized
    assert secret_kwarg not in serialized

    exc_data = event['exception']['values'][-1]
    assert exc_data['type'] == 'RuntimeError'
    assert exc_data['value'] == 'stack frame check failure'
    frames = exc_data['stacktrace']['frames']
    assert frames
    assert any(frame['function'] == '_raise_with_sensitive_locals' for frame in frames)
    assert all('vars' not in frame for frame in frames)


def test_importing_sentry_module_does_not_initialize_sentry():
    with patch('sentry_sdk.init') as mock_init:
        reloaded = importlib.reload(sentry_config)

    mock_init.assert_not_called()
    assert django_settings.SENTRY_DATA_COLLECTION == reloaded.SENTRY_DATA_COLLECTION


def test_initialize_sentry_configures_sdk_and_integrations():
    with patch('sentry_sdk.init') as mock_init:
        sentry_config.initialize_sentry(
            dsn='https://public@sentry.example.com/1',
            debug=True,
            release='abc1234',
            environment='production',
        )

    mock_init.assert_called_once()
    kwargs = mock_init.call_args.kwargs
    assert kwargs['dsn'] == 'https://public@sentry.example.com/1'
    assert kwargs['debug'] is True
    assert kwargs['release'] == 'abc1234'
    assert kwargs['environment'] == 'production'
    assert kwargs['data_collection'] is sentry_config.SENTRY_DATA_COLLECTION
    assert kwargs['ignore_errors'] == [Http404, PermissionDenied]

    integrations = kwargs['integrations']
    assert [type(integration) for integration in integrations] == [
        CeleryIntegration,
        DjangoIntegration,
        LoggingIntegration,
    ]
    logging_integration = integrations[2]
    assert logging_integration._logs_handler is None
    assert logging_integration._event_handler.level == logging.ERROR
    assert logging_integration._breadcrumb_handler.level == logging.INFO
