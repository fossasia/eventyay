import json

import pytest
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import LogEntry, UserApiToken
from eventyay.base.models.log import mask_sensitive_data


def test_mask_sensitive_data_masks_copy_only():
    raw = {
        'token': 'secret-token-12345',
        'password': 'my-password',
        'api_key': 'key-abc-xyz',
        'webhook_secret': 'whsec_9999',
        'nested': {
            'auth_token': 'nested-tok-888',
            'deep': [{'db_password': 'deep-pass', 'public_id': 42}],
        },
        'safe_field': 'public-info',
        'empty_token': '',
        'none_val': None,
        'boolean_val': True,
    }
    masked = mask_sensitive_data(raw)

    assert masked['token'] == '********'
    assert masked['password'] == '********'
    assert masked['api_key'] == '********'
    assert masked['webhook_secret'] == '********'
    assert masked['nested']['auth_token'] == '********'
    assert masked['nested']['deep'][0]['db_password'] == '********'
    assert masked['nested']['deep'][0]['public_id'] == 42
    assert masked['safe_field'] == 'public-info'
    assert masked['empty_token'] == ''
    assert masked['none_val'] is None
    assert masked['boolean_val'] is True

    # Original data dictionary is unmutated
    assert raw['token'] == 'secret-token-12345'
    assert raw['password'] == 'my-password'


def test_mask_sensitive_data_preserves_non_containers():
    assert mask_sensitive_data('string') == 'string'
    assert mask_sensitive_data(123) == 123
    assert mask_sensitive_data(None) is None


@pytest.mark.django_db
def test_user_api_token_serialize_masks_by_default(user):
    with scopes_disabled():
        token = UserApiToken.objects.create(
            name='Test Token',
            user=user,
        )
        serialized_masked = token.serialize()
        assert serialized_masked['token'] == '********'
        assert serialized_masked['name'] == 'Test Token'

        serialized_unmasked = token.serialize(mask_token=False)
        assert serialized_unmasked['token'] == token.token
        assert serialized_unmasked['token'] != '********'


@pytest.mark.django_db
def test_user_log_action_masks_secrets_and_stores_json(user):
    secret_token = 'secret-raw-token-value-1234'
    data = {
        'name': 'API Token',
        'token': secret_token,
        'settings': {'api_key': 'key-value'},
    }

    with scopes_disabled():
        user.log_action('eventyay.user.token.create', data=data)

        entry = LogEntry.objects.filter(
            action_type='eventyay.user.token.create',
            user=user,
        ).first()

        assert entry is not None
        # Raw secret token string must never appear in entry.data
        assert secret_token not in entry.data
        assert 'key-value' not in entry.data

        # json_data parsed back has masked values
        assert entry.json_data['token'] == '********'
        assert entry.json_data['settings']['api_key'] == '********'
        assert entry.json_data['name'] == 'API Token'


@pytest.mark.django_db
def test_user_token_lifecycle_audit_entries_have_no_secrets(user):
    with scopes_disabled():
        token = UserApiToken.objects.create(
            name='Deployment Bot',
            user=user,
        )
        raw_token = token.token

        # 1. Token Create
        user.log_action('eventyay.user.token.create', data=token.serialize())

        # 2. Token Upgrade
        token.version = '2'
        token.save()
        user.log_action('eventyay.user.token.upgrade', data=token.serialize())

        # 3. Token Revoke
        token.expires = now()
        token.save()
        user.log_action('eventyay.user.token.revoke', data=token.serialize())

        logs = list(
            LogEntry.objects.filter(
                user=user,
                action_type__startswith='eventyay.user.token.',
            ).order_by('datetime')
        )

        assert len(logs) == 3

        for log in logs:
            # Neither the raw database text nor json_data contains raw_token
            assert raw_token not in log.data
            assert log.json_data['token'] == '********'
            assert log.json_data['name'] == 'Deployment Bot'

        # Verify display names are localized and rendered
        assert logs[0].display() == 'A new API token was created.'
        assert logs[1].display() == 'The API token was upgraded to the latest version.'
        assert logs[2].display() == 'The API token was revoked.'


@pytest.mark.django_db
def test_log_entry_json_data_masks_historical_records(user):
    """Even if an old row was stored prior to this patch, json_data masks sensitive keys."""
    historical_raw_data = json.dumps({'name': 'Legacy', 'token': 'legacy-leak-token-999'})
    with scopes_disabled():
        entry = LogEntry.objects.create(
            content_object=user,
            user=user,
            action_type='eventyay.user.token.create',
            data=historical_raw_data,
        )

        assert entry.json_data['token'] == '********'
        assert entry.json_data['name'] == 'Legacy'

