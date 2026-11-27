import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sentry_sdk
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings as django_settings
from django.test import RequestFactory
from sentry_sdk.integrations._wsgi_common import _filter_headers
from sentry_sdk.integrations.django import DjangoRequestExtractor
from sentry_sdk.transport import Transport

from eventyay.base.models import User
from eventyay.config.asgi import PatchedSentryAsgiMiddleware
from eventyay.features.live import routing
from eventyay.features.live.consumers import MainConsumer
from eventyay.features.live.modules.auth import AuthModule
from eventyay.features.live.modules.chat import ChatModule
from eventyay.features.live.modules.room import RoomModule


class CollectingTransport(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


@asynccontextmanager
async def _noop_statsd():
    yield MagicMock()


@pytest.fixture
def sentry_transport():
    transport = CollectingTransport()
    sentry_sdk.init(
        dsn='https://public@sentry.example.com/1',
        transport=transport,
        data_collection=django_settings.SENTRY_DATA_COLLECTION,
    )
    yield transport
    sentry_sdk.get_client().close()
    sentry_sdk.init()


@pytest.fixture
def in_memory_channel_layer(settings):
    settings.CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
    settings.REDIS_USE_PUBSUB = False
    settings.SENTRY_DSN = 'https://public@sentry.example.com/1'


@pytest.mark.asyncio
async def test_concurrent_connections_keep_their_own_event_context(sentry_transport, in_memory_channel_layer):
    events = {'first': MagicMock(id=101, pk=101), 'second': MagicMock(id=202, pk=202)}

    async def ping(last_ping, user):
        sentry_sdk.capture_message('ping')
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


@asynccontextmanager
async def _broken_redis():
    raise RuntimeError('redis unavailable')
    yield


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
            with patch.object(RoomModule, '_update_view_count', new=AsyncMock()):
                await enter_room(module, {'room': room_id})
            await both_entered.wait()
            try:
                raise RuntimeError('after room enter')
            except RuntimeError as e:
                sentry_sdk.capture_exception(e)

    room_module = 'eventyay.features.live.modules.room'
    with (
        patch(f'{room_module}.is_room_visible_for_attendee_async', new=AsyncMock(return_value=True)),
        patch(f'{room_module}.start_view', new=AsyncMock(return_value=(MagicMock(), 1))),
        patch(f'{room_module}.get_channel_layer', return_value=MagicMock(group_send=AsyncMock())),
    ):
        await asyncio.gather(enter_and_report(1), enter_and_report(2))

    sentry_sdk.flush()
    rooms = sorted(event['extra']['last_room'] for event in sentry_transport.events)
    assert rooms == ['1', '2']
    assert all(event['breadcrumbs']['values'][-1]['category'] == 'room' for event in sentry_transport.events)


@pytest.mark.asyncio
async def test_concurrent_chat_commands_keep_their_own_channel(sentry_transport):
    both_dispatched = asyncio.Barrier(2)

    async def dispatch(content):
        await both_dispatched.wait()

    async def dispatch_and_report(channel_id):
        module = ChatModule(MagicMock())
        with sentry_sdk.isolation_scope():
            await module.dispatch_command(['chat.join', 1, {'channel': channel_id}])
            sentry_sdk.capture_message('chat')

    with patch('eventyay.features.live.modules.base.BaseModule.dispatch_command', side_effect=dispatch):
        await asyncio.gather(dispatch_and_report('abc'), dispatch_and_report('def'))

    sentry_sdk.flush()
    channels = sorted(event['extra']['last_channel'] for event in sentry_transport.events)
    assert channels == ['abc', 'def']


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


def test_sensitive_request_headers_are_filtered(sentry_transport):
    headers = _filter_headers(
        {
            'Authorization': 'Token abc123',
            'Cookie': 'sessionid=xyz',
            'X-CSRFToken': 'csrf',
            'X-Forwarded-For': '203.0.113.7',
            'X-Real-IP': '203.0.113.7',
            'User-Agent': 'Mozilla/5.0',
        }
    )

    assert headers == {
        'Authorization': '[Filtered]',
        'Cookie': '[Filtered]',
        'X-CSRFToken': '[Filtered]',
        'X-Forwarded-For': '[Filtered]',
        'X-Real-IP': '[Filtered]',
        'User-Agent': 'Mozilla/5.0',
    }


def test_sensitive_frame_variables_are_filtered(sentry_transport):
    def save_token(token, password, order_code):
        raise RuntimeError(f'could not save {order_code}')

    try:
        save_token('eyJhbGciOiJIUzI1NiJ9.payload.signature', 'hunter2', 'ABC12')
    except RuntimeError as e:
        sentry_sdk.capture_exception(e)

    sentry_sdk.flush()
    frame_vars = sentry_transport.events[-1]['exception']['values'][-1]['stacktrace']['frames'][-1]['vars']
    assert frame_vars['token'] == "'[Filtered]'"
    assert frame_vars['password'] == "'[Filtered]'"
    assert frame_vars['order_code'] == "'ABC12'"
