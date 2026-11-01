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


def _card_by_label(section, label):
    """Return the HTML of the single KPI card whose title is ``label``.

    Cards are siblings in the grid, each opening with a ``td-kpi-card`` ``<a>``
    or ``<div>``. We slice from the card carrying ``title="<label>"`` up to the
    next card (or the end of the grid), which is robust to nested same-tag
    children (the status card contains inner ``<div>`` elements). Extracting one
    card lets tests assert a value or link under the correct KPI rather than
    anywhere in the section.
    """
    # Opening tags of every KPI card, in order.
    starts = [m.start() for m in re.finditer(r'<(?:a|div)\b[^>]*\btd-kpi-card\b', section)]
    assert starts, 'no KPI cards found in section'
    for i, start in enumerate(starts):
        opening = section[start : section.index('>', start) + 1]
        if f'title="{label}"' in opening:
            end = starts[i + 1] if i + 1 < len(starts) else len(section)
            return section[start:end]
    raise AssertionError(f'KPI card with title {label!r} not found')


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

    # Each KPI card links to its own filtered view, asserted on the specific
    # card so swapping two cards or an identical URL elsewhere cannot pass.
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

    ordered_card = _card_by_label(section, 'Ordered attendees')
    paid_card = _card_by_label(section, 'Paid attendees')
    revenue_card = _card_by_label(section, 'Total revenue')
    waiting_card = _card_by_label(section, 'Waiting list')
    checkin_card = _card_by_label(section, 'Checked in')

    assert f'href="{orders_url}"' in ordered_card
    assert f'href="{overview_url}"' in paid_card
    assert f'href="{overview_url}"' in revenue_card
    # The waiting-list card counts no-voucher entries, so its link must carry
    # the matching status=w filter.
    assert f'href="{waitinglist_url}?status=w"' in waiting_card
    assert f'href="{checkin_url}"' in checkin_card

    # Values appear under the correct label: ordered = 3, paid = 2.
    assert re.search(r'td-kpi-value">\s*3\s*<', ordered_card)
    assert re.search(r'td-kpi-value">\s*2\s*<', paid_card)
    # A swapped value must not satisfy the other card.
    assert not re.search(r'td-kpi-value">\s*2\s*<', ordered_card)
    assert not re.search(r'td-kpi-value">\s*3\s*<', paid_card)


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
    # A live, published event must render the "live" status card.
    # ticket_component_presale_status reads the Event.tickets_published FIELD,
    # so set and save that field (not just a settings key).
    with scopes_disabled():
        event = env['event']
        event.live = True
        event.is_public = True
        event.tickets_published = True
        event.save()

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    section = _kpi_section(response.content.decode())
    # Assert the expected literal class, not the context echoing itself.
    status = response.context['at_a_glance']['ticket_shop_status']
    assert status['class'] == 'live'
    status_card = _card_by_label(section, 'Ticket shop status')
    assert 'td-status-card-live' in status_card
    # The live status text is rendered in the card.
    assert str(status['text']) in status_card


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_status_card_off_when_not_live(client, env):
    with scopes_disabled():
        event = env['event']
        event.live = False
        event.tickets_published = False
        event.save()

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    section = _kpi_section(response.content.decode())
    assert response.context['at_a_glance']['ticket_shop_status']['class'] == 'off'
    status_card = _card_by_label(section, 'Ticket shop status')
    assert 'td-status-card-off' in status_card


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_status_card_link_requires_change_permission(client, env):
    # A user who can view orders but not change settings must see the status
    # card without a "Click to change" link (EventLive needs can_change_event_settings).
    _seed_orders(env)
    with scopes_disabled():
        team = Team.objects.create(
            organizer=env['organizer'],
            can_view_orders=True,
            can_change_event_settings=False,
            all_events=True,
        )
        viewer = User.objects.create_user('viewer@example.com', 'dummy')
        team.members.add(viewer)

    client.force_login(viewer)
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    assert response.context['at_a_glance']['can_change_event_settings'] is False
    section = _kpi_section(response.content.decode())
    status_card = _card_by_label(section, 'Ticket shop status')
    live_url = reverse(
        'control:event.live',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    # Status is still shown, but not as a link to the (forbidden) live view.
    assert 'td-status-card' in status_card
    assert f'href="{live_url}"' not in status_card
    assert 'Click to change' not in status_card
    # The spacer footer is kept so the card stays the same height as the others.
    assert 'td-kpi-hint-spacer' in status_card


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_respects_subevent_filter(client, env):
    # Event series: positions attached to a subevent should be counted only
    # when that subevent is selected, and KPI links carry the subevent.
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

    # Links on the selected-date dashboard carry ?subevent=<id>.
    section1 = _kpi_section(resp1.content.decode())
    ordered_card = _card_by_label(section1, 'Ordered attendees')
    assert f'?subevent={se1.pk}' in ordered_card
    # The waiting-list link keeps the date scope AND the status=w filter,
    # joined with a valid separator (HTML-escaped as &amp; in the markup).
    waiting_card = _card_by_label(section1, 'Waiting list')
    assert f'?subevent={se1.pk}&amp;status=w' in waiting_card


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_counts_all_dates_when_no_subevent_selected(client, env):
    # For an event series with no date selected, waiting-list entries and
    # check-in lists that belong to subevents must still be counted.
    with scopes_disabled():
        event = env['event']
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])
    with scope(organizer=env['organizer'], event=env['event']):
        se1 = event.subevents.create(name='Day 1', date_from=now())
        se2 = event.subevents.create(name='Day 2', date_from=now())
        # Paid admission positions on each date.
        for code, se in (('A1', se1), ('A2', se2)):
            o = Order.objects.create(
                event=event, status=Order.STATUS_PAID, datetime=now(), expires=now(), total=25, code=code
            )
            OrderPosition.objects.create(order=o, product=env['product'], price=25, subevent=se)
        # Waiting-list entries on each date.
        WaitingListEntry.objects.create(event=event, product=env['product'], email='w1@example.com', subevent=se1)
        WaitingListEntry.objects.create(event=event, product=env['product'], email='w2@example.com', subevent=se2)
        # A per-date check-in list on each date.
        CheckinList.objects.create(event=event, name='Gate 1', all_products=True, subevent=se1)
        CheckinList.objects.create(event=event, name='Gate 2', all_products=True, subevent=se2)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))  # no subevent selected
    kpi = response.context['at_a_glance']

    # Both dates are included rather than only null-subevent records.
    assert kpi['paid_attendees'] == 2
    assert kpi['waiting_list'] == 2
    assert kpi['has_checkin_lists'] is True
    # Each list covers its own date's single paid position -> 2 distinct positions.
    assert kpi['checkin_total'] == 2


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_checkin_counts_unique_positions_across_lists(client, env):
    # A position on two overlapping all-products lists must be counted once.
    _seed_orders(env)  # 2 paid + 1 pending admission positions
    with scope(organizer=env['organizer'], event=env['event']):
        CheckinList.objects.create(event=env['event'], name='List A', all_products=True)
        CheckinList.objects.create(event=env['event'], name='List B', all_products=True)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    kpi = response.context['at_a_glance']
    # Two lists both cover the same 2 paid positions; distinct count stays 2
    # (summing per-list would wrongly give 4).
    assert kpi['checkin_total'] == 2
    assert kpi['checked_in'] == 0


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_includes_event_level_checkin_list_for_selected_subevent(client, env):
    # An event-level check-in list (subevent=None) applies to every date, so
    # when a date is selected its positions for that date must still be counted.
    with scopes_disabled():
        event = env['event']
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])
    with scope(organizer=env['organizer'], event=env['event']):
        se1 = event.subevents.create(name='Day 1', date_from=now())
        se2 = event.subevents.create(name='Day 2', date_from=now())
        for code, se in (('EL1', se1), ('EL2', se2)):
            o = Order.objects.create(
                event=event, status=Order.STATUS_PAID, datetime=now(), expires=now(), total=25, code=code
            )
            OrderPosition.objects.create(order=o, product=env['product'], price=25, subevent=se)
        # Event-level list (no subevent) -- applies to all dates.
        CheckinList.objects.create(event=event, name='All dates', all_products=True, subevent=None)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env, subevent=se1))
    kpi = response.context['at_a_glance']

    # The event-level list is included, and its positions are scoped to se1,
    # so only the single se1 position is counted (not se2's).
    assert kpi['has_checkin_lists'] is True
    assert kpi['checkin_total'] == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_checkin_list_view_includes_event_level_lists_for_selected_date(client, env):
    # The "View check-in lists" destination must show event-level lists
    # (subevent=None) when a date is selected, matching what the KPI counts.
    with scopes_disabled():
        event = env['event']
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])
    with scope(organizer=env['organizer'], event=env['event']):
        se1 = event.subevents.create(name='Day 1', date_from=now())
        se2 = event.subevents.create(name='Day 2', date_from=now())
        day_list = CheckinList.objects.create(event=event, name='Day 1 gate', all_products=True, subevent=se1)
        other_day_list = CheckinList.objects.create(event=event, name='Day 2 gate', all_products=True, subevent=se2)
        event_list = CheckinList.objects.create(event=event, name='All dates gate', all_products=True, subevent=None)

    client.force_login(env['user_with_perm'])
    url = reverse(
        'control:event.orders.checkinlists',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    response = client.get(f'{url}?subevent={se1.pk}')
    assert response.status_code == 200
    ids = {cl.pk for cl in response.context['checkinlists']}
    assert day_list.pk in ids          # the selected date's list
    assert event_list.pk in ids        # event-level list is also shown
    assert other_day_list.pk not in ids  # another date's list is excluded


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_hidden_without_order_permission(client, env):
    client.force_login(env['user_no_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    # No order permission -> at_a_glance is None and the section is not rendered.
    assert response.context['at_a_glance'] is None
    assert 'td-kpi-grid' not in response.content.decode()
