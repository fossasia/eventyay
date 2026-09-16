"""Tests for the dedicated event API area (#4440)."""

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import override_settings
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from eventyay.base.models import Team
from eventyay.base.models.organizer import TeamAPIToken
from eventyay.eventyay_common.api_catalog import (
    build_api_catalog,
    event_has_tickets_component,
    event_has_talks_component,
)
from eventyay.eventyay_common.navigation import get_event_navigation
from eventyay.eventyay_common.utils import EventCreatedFor


def _api_url(event):
    return reverse(
        'eventyay_common:event.api',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )


def _attach_session(request):
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


def _orders_only_user(organizer, event):
    user = get_user_model().objects.create_user(
        email='orders-only@example.com',
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
    return user


def test_event_navigation_includes_api(rf, event, user, team):
    path = reverse(
        'eventyay_common:event.update',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    request = _attach_session(rf.get(path))
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.resolver_match = resolve(path)

    nav = get_event_navigation(request, event)
    api_item = next(item for item in nav if str(item['label']) == 'API')
    assert api_item['url'] == _api_url(event)
    assert api_item['icon'] == 'code'


def test_event_navigation_includes_api_for_orders_permission(rf, event, organizer):
    user = _orders_only_user(organizer, event)
    path = reverse(
        'eventyay_common:event.update',
        kwargs={'organizer': event.organizer.slug, 'event': event.slug},
    )
    request = _attach_session(rf.get(path))
    request.user = user
    request.event = event
    request.organizer = event.organizer
    request.resolver_match = resolve(path)

    nav = get_event_navigation(request, event)
    assert any(str(item['label']) == 'API' for item in nav)


@override_settings(SITE_URL='https://testserver')
def test_api_page_forbidden_without_api_relevant_permission(client, event, organizer):
    """Users on an event team without API-related permissions get 403."""
    user = get_user_model().objects.create_user(
        email='giftcards-only@example.com',
        password='testpass123',
    )
    Team.objects.create(
        organizer=organizer,
        name='Gift cards only',
        all_events=True,
        can_manage_gift_cards=True,
        can_change_event_settings=False,
        can_change_items=False,
        can_view_orders=False,
        can_change_orders=False,
        can_view_vouchers=False,
        can_change_vouchers=False,
        can_checkin_orders=False,
        can_change_submissions=False,
        can_change_teams=False,
    ).members.add(user)
    client.force_login(user)
    response = client.get(_api_url(event))
    assert response.status_code == 403


@override_settings(SITE_URL='https://testserver')
def test_api_page_not_found_without_event_membership(client, event, user):
    """Users with no event team membership are rejected by control middleware as 404."""
    client.force_login(user)
    response = client.get(_api_url(event))
    assert response.status_code == 404


@override_settings(SITE_URL='https://testserver')
def test_api_page_allows_orders_permission_without_settings(client, event, organizer):
    user = _orders_only_user(organizer, event)
    client.force_login(user)
    response = client.get(_api_url(event))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Available endpoints' in content
    assert 'orders/' in content
    assert 'Token management' in content


@override_settings(SITE_URL='https://testserver')
def test_api_page_renders_for_organiser(organizer_client, event, team):
    response = organizer_client.get(_api_url(event))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'API overview' in content
    assert 'Access levels' in content
    assert 'Token management' in content
    assert 'Available endpoints' in content
    assert f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/' in content
    assert 'speakers/' in content
    assert 'submissions/' in content
    assert 'reviews/' in content
    assert 'ReDoc' not in content
    assert 'docs.eventyay.com/api/fundamentals' not in content
    assert 'docs.eventyay.com/api-reference/index.html' in content
    assert 'bound method' not in content
    assert f'/api/v1/events/{event.slug}/' in content
    assert 'Read:' in content or 'Read' in content
    assert 'Write:' in content or 'Write' in content
    assert 'Effective team permissions' in content


def test_api_catalog_hides_orders_without_permission(rf, event, organizer, user):
    Team.objects.create(
        organizer=organizer,
        name='Settings only',
        all_events=True,
        can_change_event_settings=True,
        can_view_orders=False,
        can_change_items=False,
    ).members.add(user)

    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = build_api_catalog(request, event)
    ticket_group = next((g for g in groups if g.key == 'tickets'), None)
    if ticket_group:
        names = [str(e.name) for e in ticket_group.endpoints]
        assert 'Orders' not in names
    # Products are readable with any event team token (API permission=None).
    if ticket_group:
        assert 'Products' in [str(e.name) for e in ticket_group.endpoints]


def test_api_catalog_shows_orders_with_permission(rf, event, user, team):
    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = build_api_catalog(request, event)
    ticket_group = next(g for g in groups if g.key == 'tickets')
    names = [str(e.name) for e in ticket_group.endpoints]
    assert 'Orders' in names
    assert 'Products' in names
    orders = next(e for e in ticket_group.endpoints if str(e.name) == 'Orders')
    assert orders.required_permission == 'can_view_orders'
    assert orders.write_permission == 'can_change_orders'
    assert orders.user_can_write is True
    assert orders.read_permission_label
    assert orders.write_permission_label


def test_api_catalog_read_only_orders_user(rf, event, organizer):
    user = _orders_only_user(organizer, event)
    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = build_api_catalog(request, event)
    ticket_group = next(g for g in groups if g.key == 'tickets')
    orders = next(e for e in ticket_group.endpoints if str(e.name) == 'Orders')
    assert orders.user_can_write is False
    # Public talk endpoints remain visible when the talks component is enabled.
    assert any(g.key == 'talks' for g in groups)


def test_api_catalog_talk_write_permissions(rf, event, user, team):
    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = build_api_catalog(request, event)
    talk_group = next(g for g in groups if g.key == 'talks')
    by_name = {str(e.name): e for e in talk_group.endpoints}

    assert by_name['Submissions / sessions'].write_permission == 'can_change_submissions'
    assert by_name['Tags'].write_permission == 'can_change_submissions'
    assert by_name['Tracks'].write_permission == 'can_change_event_settings'
    assert by_name['Submission types'].write_permission == 'can_change_event_settings'

    speaker_group = next(g for g in groups if g.key == 'speakers')
    assert speaker_group.endpoints[0].write_permission == 'can_change_submissions'

    schedule_group = next(g for g in groups if g.key == 'schedule')
    rooms = next(e for e in schedule_group.endpoints if str(e.name) == 'Rooms')
    assert rooms.write_permission == 'can_change_event_settings'


def test_api_catalog_hides_talks_for_tickets_only_event(rf, event, user, team):
    event.settings.set('create_for', EventCreatedFor.TICKET.value)
    assert event_has_tickets_component(event) is True
    assert event_has_talks_component(event) is False

    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = {g.key for g in build_api_catalog(request, event)}
    assert 'tickets' in groups
    assert 'talks' not in groups
    assert 'schedule' not in groups
    assert 'speakers' not in groups


def test_api_catalog_hides_tickets_for_talks_only_event(rf, event, user, team):
    event.settings.set('create_for', EventCreatedFor.TALK.value)
    assert event_has_tickets_component(event) is False
    assert event_has_talks_component(event) is True

    request = _attach_session(rf.get(_api_url(event)))
    request.user = user
    groups = {g.key for g in build_api_catalog(request, event)}
    assert 'talks' in groups
    assert 'tickets' not in groups
    assert 'attendees' not in groups


@override_settings(SITE_URL='https://testserver')
def test_api_page_hides_talk_examples_for_tickets_only(organizer_client, event, team):
    event.settings.set('create_for', EventCreatedFor.TICKET.value)
    response = organizer_client.get(_api_url(event))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Ticket orders' in content
    assert 'Talk speakers' not in content


@override_settings(SITE_URL='https://testserver')
def test_create_and_revoke_team_token_from_api_page(organizer_client, event, team):
    url = _api_url(event)
    response = organizer_client.post(
        url,
        {
            'token_action': 'create',
            'team_id': str(team.pk),
            f'token-{team.pk}-name': 'CI Token',
        },
    )
    assert response.status_code == 302
    token = TeamAPIToken.objects.get(team=team, name='CI Token', active=True)

    response = organizer_client.post(
        url,
        {
            'token_action': 'revoke',
            'team_id': str(team.pk),
            'token_id': str(token.pk),
        },
    )
    assert response.status_code == 302
    token.refresh_from_db()
    assert token.active is False


@override_settings(SITE_URL='https://testserver')
def test_revoked_team_token_cannot_call_api(organizer_client, event, team):
    url = _api_url(event)
    organizer_client.post(
        url,
        {
            'token_action': 'create',
            'team_id': str(team.pk),
            f'token-{team.pk}-name': 'Revoke Me',
        },
    )
    token = TeamAPIToken.objects.get(team=team, name='Revoke Me', active=True)
    secret = token.token

    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Token {secret}')
    event_api = (
        f'/api/v1/organizers/{event.organizer.slug}/events/{event.slug}/'
    )
    assert api.get(event_api).status_code == 200

    organizer_client.post(
        url,
        {
            'token_action': 'revoke',
            'team_id': str(team.pk),
            'token_id': str(token.pk),
        },
    )
    response = api.get(event_api)
    assert response.status_code == 401


@override_settings(SITE_URL='https://testserver')
def test_token_create_denied_without_can_change_teams(client, event, organizer):
    user = get_user_model().objects.create_user(
        email='settings-only@example.com',
        password='testpass123',
    )
    Team.objects.create(
        organizer=organizer,
        name='No team mgmt',
        all_events=True,
        can_change_event_settings=True,
        can_change_teams=False,
    ).members.add(user)
    client.force_login(user)
    response = client.post(
        _api_url(event),
        {
            'token_action': 'create',
            'team_id': '1',
            'token-1-name': 'Should fail',
        },
    )
    assert response.status_code == 302
    assert not TeamAPIToken.objects.filter(name='Should fail').exists()


@override_settings(SITE_URL='https://testserver')
def test_token_list_only_includes_event_teams(organizer_client, event, organizer, team):
    other_event = event.__class__.objects.create(
        organizer=organizer,
        name='Other',
        slug='other-event',
        date_from=event.date_from,
        currency=event.currency,
        locale=event.locale,
        live=True,
    )
    other_team = Team.objects.create(
        organizer=organizer,
        name='Other event only',
        all_events=False,
        can_change_event_settings=True,
        can_change_teams=True,
    )
    other_team.limit_events.add(other_event)
    other_team.tokens.create(name='Other token')

    response = organizer_client.get(_api_url(event))
    assert response.status_code == 200
    content = response.content.decode()
    assert team.name in content
    assert 'Other event only' not in content
    assert 'Other token' not in content
