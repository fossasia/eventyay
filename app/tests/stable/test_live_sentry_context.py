import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sentry_sdk
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from sentry_sdk.transport import Transport

from eventyay.config.asgi import PatchedSentryAsgiMiddleware
from eventyay.features.live import routing
from eventyay.features.live.consumers import MainConsumer
from eventyay.features.live.modules.chat import ChatModule


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
    sentry_sdk.init(dsn='https://public@sentry.example.com/1', transport=transport)
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


@pytest.mark.asyncio
async def test_chat_command_records_channel_on_isolation_scope(sentry_transport):
    consumer = MagicMock()
    module = ChatModule(consumer)

    with (
        sentry_sdk.isolation_scope(),
        patch('eventyay.features.live.modules.base.BaseModule.dispatch_command', new=AsyncMock()),
    ):
        await module.dispatch_command(['chat.join', 1, {'channel': 'abc'}])
        sentry_sdk.capture_message('chat')

    sentry_sdk.flush()
    assert sentry_transport.events[-1]['extra']['last_channel'] == 'abc'
