"""Tests for the tickets dashboard (control:event.index), one section per block below."""

import re
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.meetup import EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE
from eventyay.base.models import (
    Checkin,
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
        user = User.objects.create_user('with_perm@example.com', 'dummy')
        team = Team.objects.create(
            organizer=organizer,
            can_change_event_settings=True,
            can_view_orders=True,
            can_change_orders=True,
            can_change_items=True,
            all_events=True,
        )
        team.members.add(user)
        product = Product.objects.create(event=event, name='Ticket', default_price=25, admission=True, active=True)
    return {'organizer': organizer, 'event': event, 'user': user, 'product': product}


def _url(env, name='control:event.index', **kwargs):
    return reverse(name, kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug, **kwargs})


def _header_extra(content):
    """Return the inner text of the header's ``dashboard-header-extra`` element.

    Asserting against this element (rather than the whole page) keeps the tests
    from passing on content that merely appears elsewhere, e.g. the page title
    or the "Meetup organizer" panel.
    """
    match = re.search(r'<div class="text-muted dashboard-header-extra">(.*?)</div>', content, re.DOTALL)
    assert match is not None, 'dashboard-header-extra element not found'
    return match.group(1)


# --- Page header -------------------------------------------------------------


# The control middleware redirects to SITE_URL unless it matches the test client's host.
@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_shows_tickets_dashboard_title_and_event_name(client, env):
    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()

    # Modern dashboard header with the "Tickets dashboard" title.
    assert 'modern-dashboard' in content
    assert '<h2>Tickets dashboard</h2>' in content

    # Event name and date range shown inside the header element itself.
    header_extra = _header_extra(content)
    assert 'Conference 2026' in header_extra
    with scopes_disabled():
        date_range = env['event'].get_date_range_display()
    assert date_range in header_extra


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_preserves_component_link_navigation(client, env):
    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()

    # The component_link navigation (Home / Tickets / ...) is still rendered,
    # with the Tickets entry marked active.
    tickets_url = reverse(
        'control:event.index',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    assert f'href="{tickets_url}"' in content
    assert 'navigation-button' in content

    # The Tickets entry must carry the "active" class on its anchor. Tokenize
    # the class list so a value like "inactive" (which contains "active") does
    # not satisfy the assertion.
    tickets_anchor = re.search(r'<a[^>]*href="' + re.escape(tickets_url) + r'"[^>]*>', content)
    assert tickets_anchor is not None, 'Tickets navigation anchor not found'
    anchor_tag = tickets_anchor.group(0)
    class_match = re.search(r'class="([^"]*)"', anchor_tag)
    assert class_match is not None, 'Tickets anchor has no class attribute'
    assert 'active' in class_match.group(1).split()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_event_series_branch(client, env):
    with scopes_disabled():
        event = env['event']
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()
    assert '<h2>Tickets dashboard</h2>' in content
    # Event series uses the "Event series" label instead of a date range.
    assert 'Event series' in _header_extra(content)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_meetup_branch(client, env):
    with scopes_disabled():
        env['event'].settings.set(EVENT_TYPE_SETTING, MEETUP_EVENT_TYPE)

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()
    assert '<h2>Tickets dashboard</h2>' in content
    # Meetup events use the "Meetup" label in the header (not just the
    # "Meetup organizer" panel elsewhere on the page).
    assert 'Meetup' in _header_extra(content)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_header_without_date_has_no_orphaned_separator(client, env, monkeypatch):
    # When there is no displayable date range, the header must not render a
    # dangling "&middot;" after the event name.
    monkeypatch.setattr(Event, 'get_date_range_display', lambda self, *a, **kw: '')

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    content = response.content.decode()

    header_extra = _header_extra(content).strip()
    assert 'Conference 2026' in header_extra
    # No trailing separator when there is no date/metadata to show.
    assert '&middot;' not in header_extra
    assert '·' not in header_extra


# --- At a glance KPI cards ---------------------------------------------------


def _kpi_section(content):
    """Inner HTML of the "At a glance" section, so other dashboard tiles linking
    to the same URLs cannot satisfy the assertions."""
    match = re.search(
        r'<section class="td-section" aria-labelledby="td-overview-title">(.*?)</section>',
        content,
        re.DOTALL,
    )
    assert match is not None, 'KPI section (td-overview-title) not found'
    return match.group(1)


def _card(section, label):
    """HTML of the KPI card titled ``label``, sliced up to the next card."""
    starts = [m.start() for m in re.finditer(r'<(?:a|div)\b[^>]*\btd-kpi-card\b', section)]
    for i, start in enumerate(starts):
        if f'title="{label}"' in section[start : section.index('>', start) + 1]:
            end = starts[i + 1] if i + 1 < len(starts) else len(section)
            return section[start:end]
    raise AssertionError(f'KPI card with title {label!r} not found')


def _order(event, code, status=Order.STATUS_PAID, total=25):
    return Order.objects.create(event=event, status=status, datetime=now(), expires=now(), total=total, code=code)


def _make_series(env):
    """Two dates with one paid admission position each."""
    event = env['event']
    with scopes_disabled():
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])
    with scope(organizer=env['organizer'], event=event):
        se1 = event.subevents.create(name='Day 1', date_from=now())
        se2 = event.subevents.create(name='Day 2', date_from=now())
        for code, se in (('SE01', se1), ('SE02', se2)):
            OrderPosition.objects.create(order=_order(event, code), product=env['product'], price=25, subevent=se)
    return se1, se2


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_cards_values_and_links(client, env):
    event = env['event']
    with scope(organizer=env['organizer'], event=event):
        paid = _order(event, 'PAID01', total=25)
        OrderPosition.objects.create(order=paid, product=env['product'], price=25)
        # A canceled ticket inside a still-paid order is not an attendee.
        OrderPosition.objects.create(order=paid, product=env['product'], price=25, canceled=True)
        OrderPosition.objects.create(order=_order(event, 'PAID02'), product=env['product'], price=25)
        OrderPosition.objects.create(
            order=_order(event, 'PEND01', status=Order.STATUS_PENDING), product=env['product'], price=25
        )
        WaitingListEntry.objects.create(event=event, product=env['product'], email='w@example.com')

    client.force_login(env['user'])
    response = client.get(_url(env))
    assert response.status_code == 200
    kpi = response.context['at_a_glance']
    assert kpi['ordered_attendees'] == 3
    assert kpi['paid_attendees'] == 2
    assert kpi['total_revenue'] == Decimal('50.00')
    assert kpi['waiting_list'] == 1

    section = _kpi_section(response.content.decode())
    ordered_card = _card(section, 'Ordered attendees')
    assert f'href="{_url(env, "control:event.orders")}"' in ordered_card
    assert re.search(r'td-kpi-value">\s*3\s*<', ordered_card)
    assert re.search(r'td-kpi-value">\s*2\s*<', _card(section, 'Paid attendees'))
    # The waiting-list card counts no-voucher entries, so its link filters status=w.
    assert f'href="{_url(env, "control:event.orders.waitinglist")}?status=w"' in _card(section, 'Waiting list')
    # Users who can change settings get the status card as a link to the live view.
    assert f'href="{_url(env, "control:event.live")}"' in _card(section, 'Ticket shop status')
    # No check-in lists -> placeholder instead of "0 / 0".
    assert 'No check-in lists' in _card(section, 'Checked in')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_checkin_counts_distinct_positions(client, env):
    event = env['event']
    with scope(organizer=env['organizer'], event=event):
        paid = [
            OrderPosition.objects.create(order=_order(event, code), product=env['product'], price=25)
            for code in ('PAID01', 'PAID02')
        ]
        # Pending positions are excluded (include_pending defaults to False).
        OrderPosition.objects.create(
            order=_order(event, 'PEND01', status=Order.STATUS_PENDING), product=env['product'], price=25
        )
        # Two overlapping lists cover the same positions; summing per list would give 4.
        list_a = CheckinList.objects.create(event=event, name='List A', all_products=True)
        list_b = CheckinList.objects.create(event=event, name='List B', all_products=True)
        # One attendee scanned at both lists is still one person checked in.
        for cl in (list_a, list_b):
            Checkin.objects.create(position=paid[0], list=cl, type=Checkin.TYPE_ENTRY)

    client.force_login(env['user'])
    response = client.get(_url(env))
    kpi = response.context['at_a_glance']
    assert kpi['checkin_total'] == 2
    assert kpi['checked_in'] == 1
    assert re.search(r'td-kpi-value">\s*1\s*/\s*2\s*<', _kpi_section(response.content.decode()))


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_event_series_date_filter(client, env):
    se1, se2 = _make_series(env)
    event = env['event']
    with scope(organizer=env['organizer'], event=event):
        # A canceled ticket on Day 1 must not add to that date's revenue.
        OrderPosition.objects.create(
            order=Order.objects.get(code='SE01'), product=env['product'], price=25, subevent=se1, canceled=True
        )
        WaitingListEntry.objects.create(event=event, product=env['product'], email='w1@example.com', subevent=se1)
        WaitingListEntry.objects.create(event=event, product=env['product'], email='w2@example.com', subevent=se2)
        CheckinList.objects.create(event=event, name='Day 2 gate', all_products=True, subevent=se2)
        # Event-level list applies to every date.
        CheckinList.objects.create(event=event, name='All dates', all_products=True, subevent=None)

    client.force_login(env['user'])

    # No date selected: every date is counted.
    kpi = client.get(_url(env)).context['at_a_glance']
    assert kpi['paid_attendees'] == 2
    assert kpi['waiting_list'] == 2
    assert kpi['checkin_total'] == 2

    # Day 1 selected: only its records, plus the event-level list scoped to Day 1.
    response = client.get(f'{_url(env)}?subevent={se1.pk}')
    kpi = response.context['at_a_glance']
    assert kpi['paid_attendees'] == 1
    assert kpi['total_revenue'] == Decimal('25.00')
    assert kpi['waiting_list'] == 1
    assert kpi['checkin_total'] == 1

    # Card links keep the selected date.
    section = _kpi_section(response.content.decode())
    assert f'?subevent={se1.pk}' in _card(section, 'Ordered attendees')
    assert f'?subevent={se1.pk}&amp;status=w' in _card(section, 'Waiting list')


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_kpi_permissions(client, env):
    with scopes_disabled():
        viewer = User.objects.create_user('viewer@example.com', 'dummy')
        Team.objects.create(
            organizer=env['organizer'], can_view_orders=True, can_change_event_settings=False, all_events=True
        ).members.add(viewer)
        no_orders = User.objects.create_user('no_perm@example.com', 'dummy')
        Team.objects.create(
            organizer=env['organizer'], can_view_orders=False, can_change_event_settings=True, all_events=True
        ).members.add(no_orders)

    # Can view orders but not change settings: status shown, but not as a link.
    client.force_login(viewer)
    response = client.get(_url(env))
    assert response.status_code == 200
    status_card = _card(_kpi_section(response.content.decode()), 'Ticket shop status')
    assert f'href="{_url(env, "control:event.live")}"' not in status_card
    # The spacer keeps the card the same height as the others.
    assert 'td-kpi-hint-spacer' in status_card

    # Cannot view orders: the section is not rendered at all.
    client.force_login(no_orders)
    response = client.get(_url(env))
    assert response.status_code == 200
    assert response.context['at_a_glance'] is None
    assert 'td-kpi-grid' not in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_checkin_list_view_includes_event_level_lists_for_selected_date(client, env):
    # The check-in card's destination must list what the card counts.
    se1, se2 = _make_series(env)
    event = env['event']
    with scope(organizer=env['organizer'], event=event):
        day_list = CheckinList.objects.create(event=event, name='Day 1 gate', all_products=True, subevent=se1)
        other_list = CheckinList.objects.create(event=event, name='Day 2 gate', all_products=True, subevent=se2)
        event_list = CheckinList.objects.create(event=event, name='All dates', all_products=True, subevent=None)

    client.force_login(env['user'])
    response = client.get(f'{_url(env, "control:event.orders.checkinlists")}?subevent={se1.pk}')
    assert response.status_code == 200
    ids = {cl.pk for cl in response.context['checkinlists']}
    assert {day_list.pk, event_list.pk} <= ids
    assert other_list.pk not in ids


# --- Sales and capacity -----------------------------------------------------


def _get(client, env, subevent=None):
    client.force_login(env['user'])
    url = _url(env) + (f'?subevent={subevent.pk}' if subevent else '')
    response = client.get(url)
    assert response.status_code == 200
    return response


def _sales_section(response):
    m = re.search(
        r'<section class="td-section" aria-labelledby="td-sales-title">(.*?)</section>',
        response.content.decode(),
        re.DOTALL,
    )
    assert m is not None, 'Sales and capacity section not found'
    return m.group(1)


def _row(response, name):
    return next(r for r in response.context['sales_capacity']['rows'] if r['name'] == name)


def _quota(env, name, size, products=(), variations=(), **kwargs):
    with scope(organizer=env['organizer'], event=env['event']):
        q = env['event'].quotas.create(name=name, size=size, **kwargs)
        q.products.add(*products)
        q.variations.add(*variations)
        return q


def _sales_order(env, status, product, n=1, variation=None, subevent=None, canceled=0):
    """Order with ``n`` active positions plus ``canceled`` canceled ones."""
    with scope(organizer=env['organizer'], event=env['event']):
        o = Order.objects.create(
            event=env['event'],
            status=status,
            datetime=now(),
            expires=now(),
            total=25 * n,
            code=f'O{Order.objects.count():05d}',
        )
        for i in range(n + canceled):
            OrderPosition.objects.create(
                order=o, product=product, variation=variation, price=25, subevent=subevent, canceled=i >= n
            )


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
@pytest.mark.parametrize(
    'size, paid, pending, closed, status_key, remaining',
    [
        (10, 2, 1, False, 'on_sale', 7),
        (2, 2, 0, False, 'sold_out', 0),
        (1, 0, 1, False, 'pending', 0),
        (10, 2, 0, True, 'disabled', 0),  # closed: still counts orders, nothing left
        (None, 3, 0, False, 'on_sale', None),  # unlimited
    ],
)
def test_sales_row_values_and_status(client, env, size, paid, pending, closed, status_key, remaining):
    _quota(env, 'Main', size, [env['product']], closed=closed)
    if paid:
        _sales_order(env, Order.STATUS_PAID, env['product'], n=paid)
    if pending:
        _sales_order(env, Order.STATUS_PENDING, env['product'], n=pending)

    response = _get(client, env)
    row = _row(response, 'Main')
    assert (row['paid'], row['pending'], row['ordered']) == (paid, pending, paid + pending)
    assert row['capacity'] == size
    assert row['remaining'] == remaining
    assert row['status_key'] == status_key
    if size is None:
        assert '&infin;' in _sales_section(response)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_totals_count_distinct_active_positions(client, env):
    # The same product in two quotas, plus a canceled ticket in a paid order.
    _quota(env, 'All event', 100, [env['product']])
    _quota(env, 'VIP block', 10, [env['product']])
    _sales_order(env, Order.STATUS_PAID, env['product'], n=3, canceled=1)
    _sales_order(env, Order.STATUS_PENDING, env['product'], n=1)
    # A quota limited to one variation must not count the product's others.
    with scope(organizer=env['organizer'], event=env['event']):
        shirt = Product.objects.create(event=env['event'], name='Shirt', default_price=20, admission=True)
        small = shirt.variations.create(value='Small')
        large = shirt.variations.create(value='Large')
    _quota(env, 'Small shirts', 10, [shirt], [small])
    _sales_order(env, Order.STATUS_PAID, shirt, variation=small)
    _sales_order(env, Order.STATUS_PAID, shirt, variation=large)

    response = _get(client, env)
    # Each row shows its own full count...
    assert _row(response, 'All event')['paid'] == 3
    assert _row(response, 'VIP block')['paid'] == 3
    # ...but totals count each active position once: 3 tickets + 1 Small shirt.
    totals = response.context['sales_capacity']['totals']
    assert (totals['paid'], totals['pending'], totals['ordered']) == (4, 1, 5)
    # Capacity and remaining cannot be summed across overlapping quotas.
    tfoot = re.search(r'<tfoot>(.*?)</tfoot>', _sales_section(response), re.DOTALL).group(1)
    assert tfoot.count('&mdash;') == 2
    assert '<strong>5</strong>' in tfoot


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_links_match_counts(client, env):
    main = _quota(env, 'Main', 10, [env['product']])
    with scope(organizer=env['organizer'], event=env['event']):
        second = Product.objects.create(event=env['event'], name='Second', default_price=5, admission=True)
    combo = _quota(env, 'Combo', 10, [env['product'], second])

    response = _get(client, env)
    orders = _url(env, 'control:event.orders')
    row = _row(response, 'Main')
    # "Ordered" counts paid + pending, so it uses the matching 'np' filter.
    assert row['ordered_url'] == f'{orders}?product={env["product"].pk}&status=np'
    assert row['paid_url'] == f'{orders}?product={env["product"].pk}&status=p'
    assert row['pending_url'] == f'{orders}?product={env["product"].pk}&status=n'
    assert row['quota_url'] == _url(env, 'control:event.products.quotas.show', quota=main.pk)
    # A multi-product quota has no single order filter, so it links to its detail.
    combo_detail = _url(env, 'control:event.products.quotas.show', quota=combo.pk)
    assert _row(response, 'Combo')['ordered_url'] == combo_detail


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_product_names(client, env):
    with scope(organizer=env['organizer'], event=env['event']):
        shirt = Product.objects.create(event=env['event'], name='Shirt', default_price=20, admission=True)
        small = shirt.variations.create(value='Small')
        large = shirt.variations.create(value='Large')
    _quota(env, 'Sized shirts', 10, [shirt], [small, large])
    _quota(env, 'Any shirt', 10, [shirt])  # the product itself, no variations

    response = _get(client, env)
    assert _row(response, 'Sized shirts')['products'] == ['Shirt – Small', 'Shirt – Large']
    assert _row(response, 'Any shirt')['products'] == ['Shirt']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_event_series(client, env):
    event = env['event']
    with scopes_disabled():
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])
    with scope(organizer=env['organizer'], event=event):
        se1 = event.subevents.create(name='Day 1', date_from=now())
        se2 = event.subevents.create(name='Day 2', date_from=now())
    _quota(env, 'Q day1', 10, [env['product']], subevent=se1)
    _quota(env, 'Q day2', 10, [env['product']], subevent=se2)
    q_all = _quota(env, 'Q all dates', 10, [env['product']], subevent=None)
    q_all_detail = _url(env, 'control:event.products.quotas.show', quota=q_all.pk)
    _sales_order(env, Order.STATUS_PAID, env['product'], subevent=se1)
    # A workshop with a quota on Day 1 only, sold on Day 2: no row counts it.
    with scope(organizer=env['organizer'], event=event):
        workshop = Product.objects.create(event=event, name='Workshop', default_price=10, admission=True)
    _quota(env, 'Workshop day1', 10, [workshop], subevent=se1)
    _sales_order(env, Order.STATUS_PAID, workshop, subevent=se2)

    # No date selected: every quota, and each date's links keep that date.
    response = _get(client, env)
    names = {r['name'] for r in response.context['sales_capacity']['rows']}
    assert names == {'Q day1', 'Q day2', 'Q all dates', 'Workshop day1'}
    assert f'subevent={se1.pk}&' in _row(response, 'Q day1')['ordered_url']
    assert f'subevent={se2.pk}&' in _row(response, 'Q day2')['ordered_url']
    # The order list cannot filter to "no date" positions, so the all-dates
    # quota links to its detail.
    assert _row(response, 'Q all dates')['ordered_url'] == q_all_detail
    # Totals follow each quota's date: the Day 2 workshop is not counted.
    assert response.context['sales_capacity']['totals']['paid'] == 1

    # Day 1 selected: its quotas plus the all-dates quota, not Day 2.
    response = _get(client, env, subevent=se1)
    names = {r['name'] for r in response.context['sales_capacity']['rows']}
    assert names == {'Q day1', 'Q all dates', 'Workshop day1'}
    assert f'subevent={se1.pk}&' in _row(response, 'Q day1')['paid_url']
    assert _row(response, 'Q all dates')['paid_url'] == q_all_detail


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_empty_state_and_permissions(client, env):
    # No quotas: a placeholder instead of an empty table.
    response = _get(client, env)
    section = _sales_section(response)
    assert 'No quotas have been set up yet.' in section
    assert '<table' not in section

    main = _quota(env, 'Main', 10, [env['product']])
    with scopes_disabled():
        viewer = User.objects.create_user('viewer@example.com', 'dummy')
        Team.objects.create(
            organizer=env['organizer'], can_view_orders=True, can_change_items=False, all_events=True
        ).members.add(viewer)
        no_orders = User.objects.create_user('no_perm@example.com', 'dummy')
        Team.objects.create(
            organizer=env['organizer'], can_view_orders=False, can_change_event_settings=True, all_events=True
        ).members.add(no_orders)

    # Can view orders but not change items: the quota detail would be 403,
    # so the quota name is plain text; order-list links remain.
    client.force_login(viewer)
    response = client.get(_url(env))
    row = _row(response, 'Main')
    assert row['quota_url'] is None
    assert row['paid_url'].startswith(_url(env, 'control:event.orders'))
    assert _url(env, 'control:event.products.quotas.show', quota=main.pk) not in _sales_section(response)

    # Cannot view orders: the section is not rendered.
    client.force_login(no_orders)
    response = client.get(_url(env))
    assert response.status_code == 200
    assert response.context['sales_capacity'] is None
    assert 'td-sales-title' not in response.content.decode()
