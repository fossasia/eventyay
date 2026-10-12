"""Tests for Unified Event Command Center (Issue #5092)."""

import pytest
from django.test import override_settings
from django.urls import reverse
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Team


@pytest.fixture
def command_center_url(event):
    return reverse(
        'eventyay_common:event.index',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_renders_sections(organizer_client, event, organizer, command_center_url):
    """Verify that the command center renders all key sections."""
    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()

    # Layout container
    assert 'cc-dashboard' in content

    # 1. Header & Quick Info
    assert 'cc-header-top' in content
    assert 'cc-copy-btn' in content
    assert event.name in content

    # 2. Lifecycle Timeline
    assert 'dashboard-timeline' in content
    assert 'timeline-step' in content

    # 3. Action Required
    assert 'cc-action-title' in content

    # 4. At-a-glance KPIs
    assert 'cc-kpi-grid' in content
    assert 'cc-kpi-card' in content

    # 5. Component Dashboards
    assert 'cc-component-grid' in content
    assert 'cc-component-card' in content

    # 6 & 7. Milestones and Teams
    assert 'cc-milestones-card' in content
    assert 'cc-teams-card' in content

    # 8. Analytics Overview
    assert 'cc-analytics-grid' in content

    # 9. Recent Activity
    assert 'cc-activity-feed' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_context_data(organizer_client, event, command_center_url):
    """Verify that the view provides all required context dictionaries and lists."""
    response = organizer_client.get(command_center_url)
    assert response.status_code == 200

    assert 'header_data' in response.context
    assert response.context['header_data']['public_url'] is not None

    assert 'workflow_timeline' in response.context
    assert len(response.context['workflow_timeline']) == 6

    assert 'action_required' in response.context
    assert isinstance(response.context['action_required'], list)

    assert 'at_a_glance' in response.context
    assert 'component_cards' in response.context
    assert len(response.context['component_cards']) >= 3

    assert 'upcoming_milestones' in response.context
    assert 'organiser_info' in response.context
    assert 'analytics_overview' in response.context
    assert 'recent_activity' in response.context


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_action_required_cards_and_empty_state(organizer_client, event, command_center_url):
    """When setup tasks remain, cards are shown; when all clear, empty state is displayed."""
    # Initially without products, an action card for product setup is rendered
    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'cc-action-card' in content
    assert 'Setup tasks remaining' in content

    # Once a product exists, the setup action is resolved
    with scopes_disabled():
        event.products.create(name='Standard Ticket', default_price=10)

    response = organizer_client.get(command_center_url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'cc-action-empty' in content
    assert 'No action required' in content


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_command_center_permission_talk_only(client, user, organizer, event, command_center_url):
    """A talk-only team member sees talk info but no ticket or order data."""
    team = Team.objects.create(
        organizer=organizer,
        name='Talk Only Team',
        all_events=False,
        can_change_submissions=True,
        can_view_orders=False,
        can_change_items=False,
        can_change_event_settings=False,
    )
    team.limit_events.add(event)
    team.members.add(user)

    client.force_login(user)
    response = client.get(command_center_url)
    assert response.status_code == 200

    content = response.content.decode()
    # Tickets control dashboard link should NOT be present
    assert reverse('control:event.index', kwargs={'organizer': organizer.slug, 'event': event.slug}) not in content
