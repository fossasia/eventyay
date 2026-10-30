import re
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import (
    CheckinList,
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Team,
    User,
    WaitingListEntry,
)


@pytest.fixture
def env():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='Dummy', slug='dummy')
        event = Event.objects.create(
            organizer=organizer,
            name='Conference 2026',
            slug='dummy',
            date_from=now(),
            currency='USD',
            live=True,
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

        product = Product.objects.create(event=event, name='Ticket', default_price=25, admission=True, active=True)

        return {
            'organizer': organizer,
            'event': event,
            'user_with_perm': user_with_perm,
            'user_no_perm': user_no_perm,
            'product': product,
        }


def _dashboard_url(env, subevent=None):
    url = reverse(
        'control:event.index',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    if subevent is not None:
        url += f'?subevent={subevent.pk}'
    return url


def _kpi_section(content):
    """Return the inner HTML of the "At a glance" KPI section only.

    Asserting against this slice (rather than the whole page) keeps the tests
    from passing on markup that lives elsewhere on the dashboard, e.g. the
    existing widget tiles that link to the same order/check-in URLs.
    """
    match = re.search(
        r'<section class="td-section" aria-labelledby="td-overview-title">(.*?)</section>',
        content,
        re.DOTALL,
    )
    assert match is not None, 'KPI section (td-overview-title) not found'
    return match.group(1)


def _seed_orders(env):
    """Two paid admission attendees + one pending admission attendee."""
    event = env['event']
    product = env['product']
    with scope(organizer=event.organizer, event=event):
        paid1 = Order.objects.create(
            event=event, status=Order.STATUS_PAID, datetime=now(), expires=now(), total=25, code='PAID01'
        )
        paid2 = Order.objects.create(
            event=event, status=Order.STATUS_PAID, datetime=now(), expires=now(), total=25, code='PAID02'
        )
        pending = Order.objects.create(
            event=event, status=Order.STATUS_PENDING, datetime=now(), expires=now(), total=25, code='PEND01'
        )
        positions = []
        for o in (paid1, paid2, pending):
            positions.append(OrderPosition.objects.create(order=o, product=product, price=25))
    return positions


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_context_values(client, env):
    _seed_orders(env)
    with scope(organizer=env['organizer'], event=env['event']):
        WaitingListEntry.objects.create(event=env['event'], product=env['product'], email='w@example.com')

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    kpi = response.context['at_a_glance']

    # Ordered = paid + pending admission positions (3); paid = 2.
    assert kpi['ordered_attendees'] == 3
    assert kpi['paid_attendees'] == 2
    # Revenue = sum of paid Order.total (25 + 25).
    assert kpi['total_revenue'] == Decimal('50.00')
    assert kpi['waiting_list'] == 1
    assert kpi['currency'] == 'USD'
    # No check-in lists -> zero totals and the empty-state flag.
    assert kpi['checked_in'] == 0
    assert kpi['checkin_total'] == 0
    assert kpi['has_checkin_lists'] is False
    # Shop status comes from the event's ticket presale status dict.
    assert kpi['ticket_shop_status']['class'] in ('live', 'off')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_checkin_totals(client, env):
    # 2 paid + 1 pending positions; an all-products list that excludes pending
    # (include_pending defaults to False) must count the 2 paid positions.
    _seed_orders(env)
    with scope(organizer=env['organizer'], event=env['event']):
        CheckinList.objects.create(event=env['event'], name='Entrance', all_products=True)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    kpi = response.context['at_a_glance']

    assert kpi['has_checkin_lists'] is True
    assert kpi['checkin_total'] == 2
    # No check-ins have been performed yet.
    assert kpi['checked_in'] == 0


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_cards_rendered_with_links_inside_section(client, env):
    _seed_orders(env)
    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    section = _kpi_section(response.content.decode())

    # Heading and grid live inside the KPI section.
    assert 'td-kpi-grid' in section
    assert 'At a glance' in section

    # Each KPI card links to its filtered view -- asserted within the section
    # so an identical URL elsewhere on the page cannot satisfy the check.
    orders_url = reverse(
        'control:event.orders',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    overview_url = reverse(
        'control:event.orders.overview',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    waitinglist_url = reverse(
        'control:event.orders.waitinglist',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    checkin_url = reverse(
        'control:event.orders.checkinlists',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    assert f'href="{orders_url}"' in section
    assert f'href="{overview_url}"' in section
    assert f'href="{waitinglist_url}"' in section
    assert f'href="{checkin_url}"' in section

    # The rendered KPI values reflect the seeded data inside the section.
    assert re.search(r'td-kpi-value">\s*3\s*<', section)  # ordered attendees
    assert re.search(r'td-kpi-value">\s*2\s*<', section)  # paid attendees


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_checkin_card_shows_counts_when_lists_exist(client, env):
    _seed_orders(env)
    with scope(organizer=env['organizer'], event=env['event']):
        CheckinList.objects.create(event=env['event'], name='Entrance', all_products=True)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    section = _kpi_section(response.content.decode())
    # "<checked_in> / <total>" is shown when at least one list exists.
    assert re.search(r'td-kpi-value">\s*0\s*/\s*2\s*<', section)
    assert 'No check-in lists' not in section


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_checkin_card_empty_state(client, env):
    # No check-in lists -> a translated placeholder instead of "0 / 0".
    _seed_orders(env)
    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    section = _kpi_section(response.content.decode())
    assert 'No check-in lists' in section
    assert '0 / 0' not in section


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_status_card_live(client, env):
    # A live, published event renders the "live" status card class and text.
    with scopes_disabled():
        event = env['event']
        event.live = True
        event.is_public = True
        event.save()
        event.settings.set('tickets_published', True)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    section = _kpi_section(response.content.decode())
    status = response.context['at_a_glance']['ticket_shop_status']
    assert f'td-status-card-{status["class"]}' in section
    assert str(status['text']) in section


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_status_card_off_when_not_live(client, env):
    with scopes_disabled():
        event = env['event']
        event.live = False
        event.save()

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    section = _kpi_section(response.content.decode())
    assert response.context['at_a_glance']['ticket_shop_status']['class'] == 'off'
    assert 'td-status-card-off' in section


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_respects_subevent_filter(client, env):
    # Event series: positions attached to a subevent should be counted only
    # when that subevent is selected.
    with scopes_disabled():
        event = env['event']
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])
    with scope(organizer=env['organizer'], event=env['event']):
        se1 = event.subevents.create(name='Day 1', date_from=now())
        se2 = event.subevents.create(name='Day 2', date_from=now())
        order = Order.objects.create(
            event=event, status=Order.STATUS_PAID, datetime=now(), expires=now(), total=25, code='SE01'
        )
        OrderPosition.objects.create(order=order, product=env['product'], price=25, subevent=se1)

    client.force_login(env['user_with_perm'])

    # Selecting se1 counts the position; se2 does not.
    resp1 = client.get(_dashboard_url(env, subevent=se1))
    resp2 = client.get(_dashboard_url(env, subevent=se2))
    assert resp1.context['at_a_glance']['paid_attendees'] == 1
    assert resp2.context['at_a_glance']['paid_attendees'] == 0


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_hidden_without_order_permission(client, env):
    client.force_login(env['user_no_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    # No order permission -> at_a_glance is None and the section is not rendered.
    assert response.context['at_a_glance'] is None
    assert 'td-kpi-grid' not in response.content.decode()
