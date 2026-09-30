"""Tests for event navigation and expandable Event settings (#5729)."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.urls import resolve, reverse
from django_scopes import scope

from eventyay.base.models import Team
from eventyay.eventyay_common.navigation import get_event_navigation


def _attach_session(request):
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


def _create_request(rf: RequestFactory, user, event, url_name: str):
    path = reverse(
        f'eventyay_common:{url_name}',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    request = _attach_session(rf.get(path))
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.resolver_match = resolve(path)
    return request


@pytest.mark.django_db
def test_event_navigation_hierarchy_and_children(rf, event, user, team):
    request = _create_request(rf, user, event, 'event.update')
    with scope(event=event):
        nav = get_event_navigation(request, event)

    # Standalone Plugins and API must NOT appear in the top-level nav items
    top_level_labels = [str(item['label']) for item in nav]
    assert 'Plugins' not in top_level_labels
    assert 'API' not in top_level_labels

    # Event settings must exist and have children
    settings_item = next(item for item in nav if str(item['label']) == 'Event settings')
    assert settings_item['icon'] == 'wrench'
    assert 'children' in settings_item

    children_by_label = {str(c['label']): c for c in settings_item['children']}
    assert 'General' in children_by_label
    assert 'Plugins' in children_by_label
    assert 'API' in children_by_label

    # URL endpoints for children
    assert children_by_label['General']['url'] == reverse(
        'eventyay_common:event.update',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    assert children_by_label['Plugins']['url'] == reverse(
        'eventyay_common:event.plugins',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    assert children_by_label['API']['url'] == reverse(
        'eventyay_common:event.api',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )

    # Event status must remain a top-level item right after Event settings
    assert 'Event status' in top_level_labels
    settings_idx = top_level_labels.index('Event settings')
    status_idx = top_level_labels.index('Event status')
    assert status_idx == settings_idx + 1


@pytest.mark.django_db
def test_event_navigation_active_states(rf, event, user, team):
    with scope(event=event):
        # 1. Active on event.update -> General is active
        req_update = _create_request(rf, user, event, 'event.update')
        nav_update = get_event_navigation(req_update, event)
        settings_update = next(item for item in nav_update if str(item['label']) == 'Event settings')
        children_update = {str(c['label']): c for c in settings_update['children']}
        assert children_update['General']['active'] is True
        assert children_update['Plugins']['active'] is False
        assert children_update['API']['active'] is False

        # 2. Active on event.plugins -> Plugins is active
        req_plugins = _create_request(rf, user, event, 'event.plugins')
        nav_plugins = get_event_navigation(req_plugins, event)
        settings_plugins = next(item for item in nav_plugins if str(item['label']) == 'Event settings')
        children_plugins = {str(c['label']): c for c in settings_plugins['children']}
        assert children_plugins['General']['active'] is False
        assert children_plugins['Plugins']['active'] is True
        assert children_plugins['API']['active'] is False

        # 3. Active on event.api -> API is active
        req_api = _create_request(rf, user, event, 'event.api')
        nav_api = get_event_navigation(req_api, event)
        settings_api = next(item for item in nav_api if str(item['label']) == 'Event settings')
        children_api = {str(c['label']): c for c in settings_api['children']}
        assert children_api['General']['active'] is False
        assert children_api['Plugins']['active'] is False
        assert children_api['API']['active'] is True

        # 4. Active on event.live -> Event status is active, subitems inactive
        req_live = _create_request(rf, user, event, 'event.live')
        nav_live = get_event_navigation(req_live, event)
        status_item = next(item for item in nav_live if str(item['label']) == 'Event status')
        assert status_item['active'] is True
        settings_live = next(item for item in nav_live if str(item['label']) == 'Event settings')
        assert not any(c['active'] for c in settings_live['children'])


@pytest.mark.django_db
def test_event_navigation_orders_only_user_permissions(rf, event, organizer):
    user = get_user_model().objects.create_user(
        email='orders-only-nav@example.com',
        password='testpass123',
    )
    Team.objects.create(
        organizer=organizer,
        name='Orders only',
        all_events=True,
        can_change_event_settings=False,
        can_change_items=False,
        can_view_orders=True,
        can_change_orders=False,
        can_change_submissions=False,
        can_change_teams=False,
    ).members.add(user)

    request = _create_request(rf, user, event, 'event.api')
    with scope(event=event):
        nav = get_event_navigation(request, event)

    top_level_labels = [str(item['label']) for item in nav]
    # Event status requires can_change_event_settings
    assert 'Event status' not in top_level_labels

    # Event settings is shown with only API subitem
    settings_item = next(item for item in nav if str(item['label']) == 'Event settings')
    children_labels = [str(c['label']) for c in settings_item['children']]
    assert 'API' in children_labels
    assert 'General' not in children_labels
    assert 'Plugins' not in children_labels


@pytest.mark.django_db
def test_event_navigation_no_permissions(rf, event, organizer):
    user = get_user_model().objects.create_user(
        email='no-perms@example.com',
        password='testpass123',
    )
    Team.objects.create(
        organizer=organizer,
        name='No perms',
        all_events=True,
        can_change_event_settings=False,
        can_change_items=False,
        can_view_orders=False,
        can_change_orders=False,
        can_change_submissions=False,
        can_change_teams=False,
    ).members.add(user)

    request = _create_request(rf, user, event, 'event.api')
    with scope(event=event):
        nav = get_event_navigation(request, event)

    # Neither Event settings nor Event status should be in nav
    top_level_labels = [str(item['label']) for item in nav]
    assert 'Event settings' not in top_level_labels
    assert 'Event status' not in top_level_labels
