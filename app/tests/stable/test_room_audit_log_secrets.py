import json

import pytest
from django_scopes import scope

from eventyay.base.models import AuditLog, Room
from eventyay.base.models.room import mask_room_config_secrets
from eventyay.base.services.event import _create_room
from eventyay.base.services.room import save_room, soft_delete_room


# The services are wrapped in database_sync_to_async; ``.func`` is the synchronous function.
SECRETS = ('hook-s3cret', 'jitsi-s3cret', 'zoom-s3cret')
MODULE_CONFIG = [
    {
        'type': 'chat.native',
        'config': {'webhook_url': 'https://hooks.example/in', 'webhook_hmac_secret': 'hook-s3cret'},
    },
    {'type': 'call.jitsi', 'config': {'app_id': 'app', 'app_secret': 'jitsi-s3cret', 'record': True}},
    {'type': 'call.zoom', 'config': {'client_id': 'client', 'client_secret': 'zoom-s3cret'}},
]


def assert_no_secrets(audit):
    stored = json.dumps(audit.data)
    for secret in SECRETS:
        assert secret not in stored


def test_mask_room_config_secrets_masks_copy_only():
    config = {'name': 'Room', 'module_config': MODULE_CONFIG}
    masked = mask_room_config_secrets(config)
    chat, jitsi, zoom = (module['config'] for module in masked['module_config'])
    assert chat == {'webhook_url': 'https://hooks.example/in', 'webhook_hmac_secret': '********'}
    assert jitsi == {'app_id': 'app', 'app_secret': '********', 'record': True}
    assert zoom == {'client_id': 'client', 'client_secret': '********'}
    assert config['module_config'][0]['config']['webhook_hmac_secret'] == 'hook-s3cret'


def test_mask_room_config_secrets_keeps_empty_and_non_string_values():
    config = {'module_config': [{'type': 'call.zoom', 'config': {'client_secret': '', 'password_required': True}}]}
    assert mask_room_config_secrets(config) == config


@pytest.mark.parametrize('module_config', [1, 'hook-s3cret', {'chat.native': {'webhook_hmac_secret': 'hook-s3cret'}}])
def test_mask_room_config_secrets_masks_non_list_module_config(module_config):
    assert mask_room_config_secrets({'module_config': module_config}) == {'module_config': '********'}


def test_mask_room_config_secrets_handles_missing_or_malformed_modules():
    assert mask_room_config_secrets({'name': 'Room'}) == {'name': 'Room'}
    assert mask_room_config_secrets({'module_config': None}) == {'module_config': None}
    assert mask_room_config_secrets({'module_config': ['x', {'type': 'a'}]}) == {'module_config': ['x', {'type': 'a'}]}


@pytest.mark.django_db
def test_room_created_audit_entry_has_no_secrets(event, allow_all_entitlements):
    with scope(event=event):
        room, _ = _create_room.func({'event': event, 'name': 'Room', 'module_config': MODULE_CONFIG})
        audit = AuditLog.objects.get(event=event, type='event.room.added')
        assert_no_secrets(audit)
        room.refresh_from_db()
        assert room.module_config[0]['config']['webhook_hmac_secret'] == 'hook-s3cret'


@pytest.mark.django_db
def test_room_updated_audit_entry_has_no_secrets(event):
    with scope(event=event):
        room = Room.objects.create(event=event, name='Room', module_config=MODULE_CONFIG)
        old = {'name': 'Room', 'module_config': MODULE_CONFIG}
        room.name = 'Renamed'
        new = save_room.func(event, room, ['name'], old_data=old, by_user=None)
        audit = AuditLog.objects.get(event=event, type='event.room.updated')
        assert_no_secrets(audit)
        assert audit.data['new']['name'] == {'en': 'Renamed'}
        # The caller still gets the real config back.
        assert new['module_config'][0]['config']['webhook_hmac_secret'] == 'hook-s3cret'


@pytest.mark.django_db
def test_room_deleted_audit_entry_has_no_secrets(event):
    with scope(event=event):
        room = Room.objects.create(event=event, name='Room', module_config=MODULE_CONFIG)
        soft_delete_room(event, room, by_user=None)
        assert_no_secrets(AuditLog.objects.get(event=event, type='event.room.deleted'))
