from types import SimpleNamespace
from unittest.mock import patch

from django.urls import resolve, reverse

from eventyay.control.signals import nav_organizer
from eventyay.eventyay_common.navigation import get_organizer_navigation


def test_organizer_navigation_groups_hubspot_and_social_media_under_settings(rf):
    organizer = SimpleNamespace(slug='test-orga')
    path = reverse('eventyay_common:organizer.events', kwargs={'organizer': organizer.slug})
    request = rf.get(path)
    request.organizer = organizer
    request.orgapermset = {'can_change_organizer_settings', 'can_change_teams'}
    request.resolver_match = resolve(path)

    mock_hubspot_item = {
        'label': 'HubSpot',
        'url': f'/common/organizer/{organizer.slug}/hubspot/',
        'active': False,
        'icon': 'bar-chart',
    }
    mock_social_media_item = {
        'label': 'Social Media Accounts',
        'url': f'/control/organizer/{organizer.slug}/socialmedia/',
        'active': False,
        'icon': 'share-alt',
    }

    def mock_nav_organizer_send(sender, **kwargs):
        return [
            ('hubspot', [mock_hubspot_item]),
            ('socialmedia', [mock_social_media_item]),
        ]

    with patch.object(nav_organizer, 'send', side_effect=mock_nav_organizer_send):
        nav = get_organizer_navigation(request)

    # 1. Verify top-level items do NOT contain HubSpot or Social Media Accounts
    top_level_labels = [str(item['label']) for item in nav]
    assert 'HubSpot' not in top_level_labels
    assert 'Social Media Accounts' not in top_level_labels

    # 2. Verify Settings menu exists and contains children in the exact required order
    settings_item = next((item for item in nav if str(item['label']) == 'Settings'), None)
    assert settings_item is not None
    assert 'children' in settings_item

    child_labels = [str(child['label']) for child in settings_item['children']]
    assert child_labels == ['General', 'Billing settings', 'HubSpot', 'Social Media Accounts']

    # 3. Verify URLs of children
    assert settings_item['children'][0]['url'] == reverse(
        'eventyay_common:organizer.edit', kwargs={'organizer': organizer.slug}
    )
    assert settings_item['children'][1]['url'] == reverse(
        'eventyay_common:organizer.billing', kwargs={'organizer': organizer.slug}
    )
    assert settings_item['children'][2]['url'] == f'/common/organizer/{organizer.slug}/hubspot/'
    assert settings_item['children'][3]['url'] == f'/control/organizer/{organizer.slug}/socialmedia/'


def test_organizer_navigation_when_only_hubspot_available(rf):
    organizer = SimpleNamespace(slug='test-orga')
    path = reverse('eventyay_common:organizer.events', kwargs={'organizer': organizer.slug})
    request = rf.get(path)
    request.organizer = organizer
    request.orgapermset = {'can_change_organizer_settings'}
    request.resolver_match = resolve(path)

    mock_hubspot_item = {
        'label': 'HubSpot',
        'url': f'/common/organizer/{organizer.slug}/hubspot/',
        'active': False,
        'icon': 'bar-chart',
    }

    def mock_nav_organizer_send(sender, **kwargs):
        return [
            ('hubspot', [mock_hubspot_item]),
        ]

    with patch.object(nav_organizer, 'send', side_effect=mock_nav_organizer_send):
        nav = get_organizer_navigation(request)

    settings_item = next((item for item in nav if str(item['label']) == 'Settings'), None)
    assert settings_item is not None
    child_labels = [str(child['label']) for child in settings_item['children']]
    assert child_labels == ['General', 'Billing settings', 'HubSpot']


def test_organizer_navigation_when_only_social_media_available(rf):
    organizer = SimpleNamespace(slug='test-orga')
    path = reverse('eventyay_common:organizer.events', kwargs={'organizer': organizer.slug})
    request = rf.get(path)
    request.organizer = organizer
    request.orgapermset = {'can_change_organizer_settings'}
    request.resolver_match = resolve(path)

    mock_social_media_item = {
        'label': 'Social Media Accounts',
        'url': f'/control/organizer/{organizer.slug}/socialmedia/',
        'active': False,
        'icon': 'share-alt',
    }

    def mock_nav_organizer_send(sender, **kwargs):
        return [
            ('socialmedia', [mock_social_media_item]),
        ]

    with patch.object(nav_organizer, 'send', side_effect=mock_nav_organizer_send):
        nav = get_organizer_navigation(request)

    settings_item = next((item for item in nav if str(item['label']) == 'Settings'), None)
    assert settings_item is not None
    child_labels = [str(child['label']) for child in settings_item['children']]
    assert child_labels == ['General', 'Billing settings', 'Social Media Accounts']


def test_organizer_navigation_active_state_for_settings_children(rf):
    organizer = SimpleNamespace(slug='test-orga')
    path = reverse('eventyay_common:organizer.edit', kwargs={'organizer': organizer.slug})
    request = rf.get(path)
    request.organizer = organizer
    request.orgapermset = {'can_change_organizer_settings'}
    request.resolver_match = resolve(path)

    mock_hubspot_item = {
        'label': 'HubSpot',
        'url': f'/common/organizer/{organizer.slug}/hubspot/',
        'active': True,
        'icon': 'bar-chart',
    }
    mock_social_media_item = {
        'label': 'Social Media Accounts',
        'url': f'/control/organizer/{organizer.slug}/socialmedia/',
        'active': False,
        'icon': 'share-alt',
    }

    def mock_nav_organizer_send(sender, **kwargs):
        return [
            ('hubspot', [mock_hubspot_item]),
            ('socialmedia', [mock_social_media_item]),
        ]

    with patch.object(nav_organizer, 'send', side_effect=mock_nav_organizer_send):
        nav = get_organizer_navigation(request)

    settings_item = next((item for item in nav if str(item['label']) == 'Settings'), None)
    assert settings_item is not None

    hubspot_child = next((c for c in settings_item['children'] if str(c['label']) == 'HubSpot'), None)
    assert hubspot_child is not None
    assert hubspot_child['active'] is True

    sm_child = next((c for c in settings_item['children'] if str(c['label']) == 'Social Media Accounts'), None)
    assert sm_child is not None
    assert sm_child['active'] is False


def test_organizer_navigation_without_settings_permission(rf):
    organizer = SimpleNamespace(slug='test-orga')
    path = reverse('eventyay_common:organizer.events', kwargs={'organizer': organizer.slug})
    request = rf.get(path)
    request.organizer = organizer
    request.orgapermset = {'can_change_teams'}
    request.resolver_match = resolve(path)

    mock_hubspot_item = {
        'label': 'HubSpot',
        'url': f'/common/organizer/{organizer.slug}/hubspot/',
        'active': False,
        'icon': 'bar-chart',
    }
    mock_social_media_item = {
        'label': 'Social Media Accounts',
        'url': f'/control/organizer/{organizer.slug}/socialmedia/',
        'active': False,
        'icon': 'share-alt',
    }

    def mock_nav_organizer_send(sender, **kwargs):
        return [
            ('hubspot', [mock_hubspot_item]),
            ('socialmedia', [mock_social_media_item]),
        ]

    with patch.object(nav_organizer, 'send', side_effect=mock_nav_organizer_send):
        nav = get_organizer_navigation(request)

    top_level_labels = [str(item['label']) for item in nav]
    assert 'Settings' not in top_level_labels
    assert 'HubSpot' not in top_level_labels
    assert 'Social Media Accounts' not in top_level_labels


def test_organizer_navigation_other_plugins_preserved(rf):
    organizer = SimpleNamespace(slug='test-orga')
    path = reverse('eventyay_common:organizer.events', kwargs={'organizer': organizer.slug})
    request = rf.get(path)
    request.organizer = organizer
    request.orgapermset = {'can_change_organizer_settings'}
    request.resolver_match = resolve(path)

    mock_other_plugin_item = {
        'label': 'Custom Plugin',
        'url': f'/common/organizer/{organizer.slug}/custom/',
        'active': False,
        'icon': 'plug',
    }

    def mock_nav_organizer_send(sender, **kwargs):
        return [
            ('custom_plugin', [mock_other_plugin_item]),
        ]

    with patch.object(nav_organizer, 'send', side_effect=mock_nav_organizer_send):
        nav = get_organizer_navigation(request)

    top_level_labels = [str(item['label']) for item in nav]
    assert 'Custom Plugin' in top_level_labels
