from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eventyay.features.live.consumers import MainConsumer


@asynccontextmanager
async def _noop_statsd():
    yield MagicMock()


@pytest.mark.asyncio
async def test_fatal_async_error_omits_previous_command_id():
    consumer = MainConsumer()
    consumer.content = ['room.enter', 42, {}]
    consumer.conn_time = 0
    consumer.event = None
    consumer.close = AsyncMock()
    component = MagicMock()
    component.dispatch_event = AsyncMock(side_effect=RuntimeError('boom'))
    consumer.components = {'room': component}
    sent = []

    async def capture(content, close=False):
        sent.append(content)

    consumer.send_json = capture

    with (
        patch('eventyay.features.live.consumers.statsd', _noop_statsd),
        patch('eventyay.features.live.consumers.asyncio.sleep', new=AsyncMock()),
        patch('eventyay.features.live.consumers.capture_exception'),
        patch('eventyay.features.live.consumers.log_event'),
        patch('eventyay.features.live.consumers.settings') as settings,
    ):
        settings.SENTRY_DSN = ''
        await consumer.dispatch({'type': 'room.update'})

    assert sent == [
        ['error', {'code': 'server.fatal', 'message': 'Fatal Server Error'}]
    ]


@pytest.mark.asyncio
async def test_command_error_keeps_request_identifier():
    consumer = MainConsumer()
    consumer.event = MagicMock(pk=1)
    consumer.user = object()
    consumer._maybe_refresh = AsyncMock()
    component = MagicMock()
    component.dispatch_command = AsyncMock(side_effect=RuntimeError('boom'))
    consumer.components = {'room': component}
    sent = []

    async def capture(content, close=False):
        sent.append(content)

    consumer.send_json = capture

    with (
        patch('eventyay.features.live.consumers.statsd', _noop_statsd),
        patch('eventyay.features.live.consumers.capture_exception'),
        patch('eventyay.features.live.consumers.log_event'),
        patch('eventyay.features.live.consumers.settings') as settings,
    ):
        settings.SENTRY_DSN = ''
        await consumer.receive_json(['room.enter', 7, {}])

    assert sent == [
        [
            'error',
            7,
            {'code': 'command.error', 'message': 'Failed to process request'},
        ]
    ]
