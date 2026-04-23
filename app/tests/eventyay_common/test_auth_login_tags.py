import pytest
from eventyay.eventyay_common.templatetags.auth_login_tags import get_login_context
from eventyay.base.settings import GlobalSettingsObject


@pytest.mark.django_db
def test_get_login_context_no_providers(rf):
    # Ensure no providers are enabled
    gs = GlobalSettingsObject()
    gs.settings.set('login_providers', {})

    request = rf.get('/')
    context = {'request': request}
    result = get_login_context(context)

    assert result['enabled_providers'] == []
    assert result['preferred_provider'] is None
    assert result['has_oauth_providers'] is False
    assert result['has_secondary_oauth_providers'] is False
    assert isinstance(result['show_native_login'], bool)
    assert isinstance(result['show_login_form'], bool)


@pytest.mark.django_db
def test_get_login_context_with_providers(rf):
    gs = GlobalSettingsObject()
    providers = {
        'google': {
            'state': True,
            'client_id': 'cid',
            'secret': 'sec',
            'is_preferred': True
        },
        'mediawiki': {
            'state': True,
            'client_id': 'cid2',
            'secret': 'sec2',
            'is_preferred': False
        }
    }
    gs.settings.set('login_providers', providers)

    request = rf.get('/')
    context = {'request': request}
    result = get_login_context(context)

    assert len(result['enabled_providers']) == 2
    assert result['preferred_provider'] == 'google'
    assert result['has_oauth_providers'] is True
    assert result['has_secondary_oauth_providers'] is True
    assert result['enabled_providers'][0][0] == 'google'


@pytest.mark.django_db
def test_get_login_context_unconfigured_providers(rf):
    gs = GlobalSettingsObject()
    providers = {
        'google': {
            'state': True,
            'client_id': '',  # Unconfigured
            'secret': '',
            'is_preferred': True
        }
    }
    gs.settings.set('login_providers', providers)

    request = rf.get('/')
    context = {'request': request}
    result = get_login_context(context)

    # Should be filtered out by order_login_providers/get_preferred_provider
    assert result['enabled_providers'] == []
    assert result['preferred_provider'] is None
