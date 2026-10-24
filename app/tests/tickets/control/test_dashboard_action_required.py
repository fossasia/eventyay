import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, Organizer, Team, User


@pytest.fixture
def env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=organizer,
            name='Dummy Event',
            slug='dummy',
            date_from=now(),
        )
        user_with_perm = User.objects.create_user('with_perm@example.com', 'dummy')
        team_with_perm = Team.objects.create(
            organizer=organizer,
            can_change_event_settings=True,
            can_view_orders=True,
            can_change_orders=True,
            all_events=True,
        )
        team_with_perm.members.add(user_with_perm)

        user_no_perm = User.objects.create_user('no_perm@example.com', 'dummy')
        team_no_perm = Team.objects.create(
            organizer=organizer,
            can_change_event_settings=True,
            can_view_orders=False,
            all_events=True,
        )
        team_no_perm.members.add(user_no_perm)

        return {
            'organizer': organizer,
            'event': event,
            'user_with_perm': user_with_perm,
            'user_no_perm': user_no_perm,
        }


def _dashboard_url(env):
    return reverse(
        'control:event.index',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )


def _create_pending_approval(event):
    with scopes_disabled():
        Order.objects.create(
            event=event,
            status=Order.STATUS_PENDING,
            require_approval=True,
            datetime=now(),
            expires=now(),
            total=10,
            code='APR01',
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_action_required_hidden_when_nothing_needs_attention(client, env):
    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    assert 'td-attention-title' not in response.content.decode()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_action_required_lists_pending_approvals(client, env):
    _create_pending_approval(env['event'])

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'td-attention-title' in content
    assert 'Action required' in content
    assert 'Approval pending' in content
    assert 'td-action-card td-action-warning' in content
    orders_url = reverse(
        'control:event.orders',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    assert f'href="{orders_url}?status=pa" class="td-action-btn">Show orders pending approval</a>' in content


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_action_required_hidden_without_order_permission(client, env):
    _create_pending_approval(env['event'])

    client.force_login(env['user_no_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    assert 'td-attention-title' not in response.content.decode()
