import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scopes_disabled

from eventyay.base.models import (
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Team,
    User,
)
from eventyay.plugins.statistics.signals import clear_cache


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

        product = Product.objects.create(event=event, name='Ticket', default_price=10, admission=True)

        return {
            'organizer': organizer,
            'event': event,
            'user_with_perm': user_with_perm,
            'user_no_perm': user_no_perm,
            'product': product,
        }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_dashboard_shows_statistics_only_to_order_viewers(client, env):
    event = env['event']
    organizer = env['organizer']
    product = env['product']

    with scopes_disabled():
        order = Order.objects.create(
            event=event,
            status=Order.STATUS_PAID,
            datetime=now(),
            expires=now(),
            total=10,
            code='TST01',
        )
        OrderPosition.objects.create(
            order=order,
            product=product,
            price=10,
        )

    url = reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )

    # 1. User WITH permission gets statistics chart markup
    client.force_login(env['user_with_perm'])
    response = client.get(url)
    assert response.status_code == 200
    assert 'obd_chart' in response.content.decode()

    # 2. User WITHOUT permission gets NO statistics chart markup
    client.force_login(env['user_no_perm'])
    response = client.get(url)
    assert response.status_code == 200
    assert 'obd_chart' not in response.content.decode()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_legacy_statistics_url_redirects_to_dashboard(client, env):
    organizer = env['organizer']
    event = env['event']

    client.force_login(env['user_with_perm'])
    redirect_url = reverse(
        'control:event.statistics.redirect',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    response = client.get(redirect_url)

    assert response.status_code == 301
    expected_target = reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )
    assert response.url == expected_target


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_dashboard_statistics_hidden_when_no_orders(client, env):
    event = env['event']
    organizer = env['organizer']

    url = reverse(
        'control:event.index',
        kwargs={'organizer': organizer.slug, 'event': event.slug},
    )

    client.force_login(env['user_with_perm'])
    response = client.get(url)
    assert response.status_code == 200
    # Zero orders -> no statistics section or chart rendered
    assert 'obd_chart' not in response.content.decode()


@pytest.mark.django_db
@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test-statistics-cache',
        }
    }
)
def test_statistics_cache_invalidation(env):
    with scopes_disabled():
        event = Event.objects.get(pk=env['event'].pk)
        event.cache.set('statistics_obd_dataall', 'cached_data')
        assert event.cache.get('statistics_obd_dataall') == 'cached_data'

        clear_cache(event)

        assert event.cache.get('statistics_obd_dataall') is None
