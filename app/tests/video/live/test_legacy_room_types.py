import uuid
from contextlib import asynccontextmanager

import pytest
from channels.db import database_sync_to_async
from tests.video.utils import LoggingCommunicator, get_token
from venueless.core.models import Room
from venueless.routing import application

from eventyay.base.services.room import UNSUPPORTED_CREATE_MODULE_TYPES


@asynccontextmanager
async def world_communicator(token=None):
    communicator = LoggingCommunicator(application, '/ws/world/sample/')
    await communicator.connect()
    if token:
        await communicator.send_json_to(['authenticate', {'token': token}])
    else:
        await communicator.send_json_to(
            ['authenticate', {'client_id': str(uuid.uuid4())}]
        )
    response = await communicator.receive_json_from()
    assert response[0] == 'authenticated', response
    communicator.context = response[1]
    assert 'world.config' in response[1], response
    try:
        yield communicator
    finally:
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize('module_type', sorted(UNSUPPORTED_CREATE_MODULE_TYPES))
async def test_room_create_rejects_removed_room_types(world, module_type):
    async with world_communicator(token=get_token(world, ['admin'])) as c:
        await c.send_json_to(
            [
                'room.create',
                123,
                {
                    'name': f'Legacy {module_type}',
                    'description': 'should not be created',
                    'modules': [{'type': module_type}],
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == 'error'
        assert response[2]['code'] == 'room.invalid.unsupported_type'


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize('module_type', sorted(UNSUPPORTED_CREATE_MODULE_TYPES))
async def test_room_config_patch_rejects_new_removed_room_types(world, module_type):
    empty_room = await database_sync_to_async(Room.objects.create)(
        event=world,
        name='Unconfigured',
        module_config=[],
    )
    async with world_communicator(token=get_token(world, ['admin'])) as c:
        await c.send_json_to(
            [
                'room.config.patch',
                123,
                {
                    'room': str(empty_room.pk),
                    'module_config': [{'type': module_type, 'config': {}}],
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == 'error'
        assert response[2]['code'] == 'room.invalid.unsupported_type'


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_existing_exhibition_rooms_remain_editable(world, exhibition_room):
    async with world_communicator(token=get_token(world, ['admin'])) as c:
        await c.send_json_to(
            [
                'room.config.patch',
                123,
                {
                    'room': str(exhibition_room.pk),
                    'name': 'Exhibition still works',
                    'module_config': exhibition_room.module_config,
                },
            ]
        )
        response = await c.receive_json_from()
        assert response[0] == 'success'
        await database_sync_to_async(exhibition_room.refresh_from_db)()
        assert exhibition_room.name == 'Exhibition still works'


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_existing_exhibition_rooms_can_still_be_entered(world, exhibition_room):
    async with world_communicator() as c:
        await c.send_json_to(['room.enter', 123, {'room': str(exhibition_room.pk)}])
        response = await c.receive_json_from()
        assert response[0] == 'success'
