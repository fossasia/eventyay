"""Tests for quick setup view and dashboard widget permission checks."""

import pytest

from eventyay.base.models import Team


pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures('allow_all_entitlements')]


@pytest.fixture(autouse=True)
def _use_testserver_site_url(settings):
    settings.SITE_URL = 'https://testserver'


def _login_team_member(client, organizer, event, user, **permissions):
    team = Team.objects.create(organizer=organizer, name='Quick Setup Test Team', **permissions)
    team.limit_events.add(event)
    team.members.add(user)
    client.force_login(user)
    return client


def test_quick_setup_requires_change_event_settings(client, organizer, event, user):
    _login_team_member(client, organizer, event, user, can_view_orders=True, can_change_event_settings=False)
    url = f'/control/event/{organizer.slug}/{event.slug}/quickstart/'

    assert client.get(url).status_code == 403
    assert client.post(url, {}).status_code == 403


def test_quick_setup_allowed_with_change_event_settings(client, organizer, event, user):
    _login_team_member(client, organizer, event, user, can_change_event_settings=True)
    url = f'/control/event/{organizer.slug}/{event.slug}/quickstart/'

    assert client.get(url).status_code == 200


def test_dashboard_hides_setup_ticketing_without_event_settings(client, organizer, event, user):
    _login_team_member(client, organizer, event, user, can_view_orders=True, can_change_event_settings=False)
    dashboard_url = f'/control/event/{organizer.slug}/{event.slug}/'
    quickstart_url = f'/control/event/{organizer.slug}/{event.slug}/quickstart/'

    resp = client.get(dashboard_url)
    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'Set up Ticketing' not in content
    assert quickstart_url not in content


def test_dashboard_shows_setup_ticketing_with_event_settings(client, organizer, event, user):
    _login_team_member(client, organizer, event, user, can_view_orders=True, can_change_event_settings=True)
    dashboard_url = f'/control/event/{organizer.slug}/{event.slug}/'
    quickstart_url = f'/control/event/{organizer.slug}/{event.slug}/quickstart/'

    resp = client.get(dashboard_url)
    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'Set up Ticketing' in content
    assert quickstart_url in content
