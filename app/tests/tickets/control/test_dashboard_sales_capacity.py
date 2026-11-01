import re

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import (
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
    Team,
    User,
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

    # Product/Quota are organizer-scoped, so create event-owned data under an
    # active tenant scope rather than scopes_disabled().
    with scope(organizer=organizer, event=event):
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


def _sales_section(content):
    """Inner HTML of the Sales and capacity section only."""
    m = re.search(
        r'<section class="td-section" aria-labelledby="td-sales-title">(.*?)</section>',
        content,
        re.DOTALL,
    )
    assert m is not None, 'Sales and capacity section not found'
    return m.group(1)


def _row_by_name(section, quota_name):
    """Return the <tr> whose name cell links a quota called quota_name."""
    for m in re.finditer(r'<tr>(.*?)</tr>', section, re.DOTALL):
        row = m.group(0)
        if f'>{quota_name}</a>' in row:
            return row
    raise AssertionError(f'row for quota {quota_name!r} not found')


def _tfoot(section):
    m = re.search(r'<tfoot>(.*?)</tfoot>', section, re.DOTALL)
    assert m is not None, 'tfoot (total row) not found'
    return m.group(1)


def _make_quota(env, name, size, products, **kwargs):
    with scope(organizer=env['organizer'], event=env['event']):
        q = env['event'].quotas.create(name=name, size=size, **kwargs)
        for p in products:
            q.products.add(p)
        return q


def _make_order(env, status, product, n=1, subevent=None):
    with scope(organizer=env['organizer'], event=env['event']):
        o = Order.objects.create(
            event=env['event'], status=status, datetime=now(), expires=now(),
            total=25 * n, code=f'{status.upper()}{Order.objects.count():04d}',
        )
        for _ in range(n):
            OrderPosition.objects.create(order=o, product=product, price=25, subevent=subevent)
        return o


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_row_values(client, env):
    # Capacity 10; 2 paid + 1 pending admission positions -> remaining 7.
    _make_quota(env, 'Main', 10, [env['product']])
    _make_order(env, Order.STATUS_PAID, env['product'], n=2)
    _make_order(env, Order.STATUS_PENDING, env['product'], n=1)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    sc = response.context['sales_capacity']
    assert sc['has_quotas'] is True
    row = next(r for r in sc['rows'] if r['name'] == 'Main')
    assert row['paid'] == 2
    assert row['pending'] == 1
    assert row['ordered'] == 3
    assert row['capacity'] == 10
    assert row['remaining'] == 7
    assert row['status_key'] == 'on_sale'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_status_sold_out(client, env):
    # Capacity 2, 2 paid -> gone/sold out.
    _make_quota(env, 'Tiny', 2, [env['product']])
    _make_order(env, Order.STATUS_PAID, env['product'], n=2)

    client.force_login(env['user_with_perm'])
    sc = client.get(_dashboard_url(env)).context['sales_capacity']
    row = next(r for r in sc['rows'] if r['name'] == 'Tiny')
    assert row['remaining'] == 0
    assert row['status_key'] == 'sold_out'
    assert row['status_dot'] == 'td-dot-danger'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_status_zero_capacity(client, env):
    # A quota with size=0 is sold out (remaining 0) even with no orders.
    _make_quota(env, 'Zero', 0, [env['product']])

    client.force_login(env['user_with_perm'])
    sc = client.get(_dashboard_url(env)).context['sales_capacity']
    row = next(r for r in sc['rows'] if r['name'] == 'Zero')
    assert row['capacity'] == 0
    assert row['remaining'] == 0
    assert row['ordered'] == 0
    assert row['status_key'] == 'sold_out'
    assert row['status_dot'] == 'td-dot-danger'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_status_pending_only(client, env):
    # Capacity 1, 1 pending (no paid) -> AVAILABILITY_ORDERED (sold out pending).
    _make_quota(env, 'OnePending', 1, [env['product']])
    _make_order(env, Order.STATUS_PENDING, env['product'], n=1)

    client.force_login(env['user_with_perm'])
    sc = client.get(_dashboard_url(env)).context['sales_capacity']
    row = next(r for r in sc['rows'] if r['name'] == 'OnePending')
    assert row['status_key'] == 'pending'
    assert row['remaining'] == 0


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_status_disabled_when_closed(client, env):
    q = _make_quota(env, 'Closed', 10, [env['product']])
    with scope(organizer=env['organizer'], event=env['event']):
        q.closed = True
        q.save()

    client.force_login(env['user_with_perm'])
    sc = client.get(_dashboard_url(env)).context['sales_capacity']
    row = next(r for r in sc['rows'] if r['name'] == 'Closed')
    assert row['status_key'] == 'disabled'
    assert row['status_dot'] == 'td-dot-neutral'


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_unlimited_capacity(client, env):
    # size=None -> unlimited capacity and remaining rendered as infinity.
    _make_quota(env, 'Unlimited', None, [env['product']])
    _make_order(env, Order.STATUS_PAID, env['product'], n=3)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    sc = response.context['sales_capacity']
    row = next(r for r in sc['rows'] if r['name'] == 'Unlimited')
    assert row['capacity'] is None
    assert row['remaining'] is None
    assert row['status_key'] == 'on_sale'

    # The rendered row shows the infinity glyph in capacity/remaining.
    section = _sales_section(response.content.decode())
    rendered = _row_by_name(section, 'Unlimited')
    assert '&infin;' in rendered


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_total_row(client, env):
    _make_quota(env, 'A', 10, [env['product']])
    bprod = None
    with scope(organizer=env['organizer'], event=env['event']):
        bprod = Product.objects.create(event=env['event'], name='B ticket', default_price=5, admission=True)
    _make_quota(env, 'B', 20, [bprod])
    _make_order(env, Order.STATUS_PAID, env['product'], n=2)
    _make_order(env, Order.STATUS_PAID, bprod, n=4)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    sc = response.context['sales_capacity']
    # Totals over distinct positions: 2 + 4 paid across non-overlapping quotas.
    assert sc['totals']['paid'] == 6
    assert sc['totals']['ordered'] == 6
    assert sc['totals']['pending'] == 0
    # Capacity/remaining cannot be summed across overlapping quotas -> omitted.
    assert sc['totals']['capacity'] == 'n/a'
    assert sc['totals']['remaining'] == 'n/a'

    tfoot = _tfoot(_sales_section(response.content.decode()))
    assert '<strong>6</strong>' in tfoot   # ordered + paid totals both 6
    assert '&mdash;' in tfoot               # capacity/remaining shown as dash


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_totals_distinct_across_overlapping_quotas(client, env):
    # A product in two quotas must not be counted twice in the totals, even
    # though each quota row shows the full count for that product.
    _make_quota(env, 'All event', 100, [env['product']])
    _make_quota(env, 'VIP block', 10, [env['product']])
    _make_order(env, Order.STATUS_PAID, env['product'], n=3)
    _make_order(env, Order.STATUS_PENDING, env['product'], n=1)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    sc = response.context['sales_capacity']

    # Each row shows the product's full counts (3 paid, 1 pending).
    for name in ('All event', 'VIP block'):
        row = next(r for r in sc['rows'] if r['name'] == name)
        assert row['paid'] == 3
        assert row['pending'] == 1

    # But the totals count DISTINCT positions, not 3+3 / 1+1.
    assert sc['totals']['paid'] == 3
    assert sc['totals']['pending'] == 1
    assert sc['totals']['ordered'] == 4


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_totals_exclude_out_of_quota_variations(client, env):
    # A quota restricted to one variation must not make the totals count
    # positions of the product's other variations.
    with scope(organizer=env['organizer'], event=env['event']):
        shirt = Product.objects.create(event=env['event'], name='Shirt', default_price=20, admission=True)
        v_small = shirt.variations.create(value='Small')
        v_large = shirt.variations.create(value='Large')
    with scope(organizer=env['organizer'], event=env['event']):
        q = env['event'].quotas.create(name='Small shirts', size=10)
        q.variations.add(v_small)  # quota covers ONLY the Small variation
        # One paid Small position (in quota) and one paid Large position (NOT).
        o = Order.objects.create(
            event=env['event'], status=Order.STATUS_PAID, datetime=now(), expires=now(), total=40, code='SHIRT1'
        )
        OrderPosition.objects.create(order=o, product=shirt, variation=v_small, price=20)
        OrderPosition.objects.create(order=o, product=shirt, variation=v_large, price=20)

    client.force_login(env['user_with_perm'])
    sc = client.get(_dashboard_url(env)).context['sales_capacity']
    # Only the Small position counts; the Large position is outside the quota.
    assert sc['totals']['paid'] == 1


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_total_row_unlimited_footer(client, env):
    # Capacity/remaining totals are not summable -> rendered as a dash, never
    # as 0 or a bogus number, even when a quota is unlimited.
    _make_quota(env, 'Limited', 10, [env['product']])
    _make_quota(env, 'Infinite', None, [env['product']])
    _make_order(env, Order.STATUS_PAID, env['product'], n=2)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    sc = response.context['sales_capacity']
    assert sc['totals']['capacity'] == 'n/a'
    assert sc['totals']['remaining'] == 'n/a'
    assert sc['totals']['paid'] == 2  # distinct positions, not doubled

    tfoot = _tfoot(_sales_section(response.content.decode()))
    # Capacity/remaining render as a dash (not a number, not infinity).
    assert tfoot.count('&mdash;') == 2
    assert '&infin;' not in tfoot


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_links_match_counts(client, env):
    _make_quota(env, 'Main', 10, [env['product']])
    _make_order(env, Order.STATUS_PAID, env['product'], n=1)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    section = _sales_section(response.content.decode())
    row = _row_by_name(section, 'Main')

    orders_url = reverse(
        'control:event.orders',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug},
    )
    with scope(organizer=env['organizer'], event=env['event']):
        quota_pk = env['event'].quotas.first().pk
    quota_url = reverse(
        'control:event.products.quotas.show',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug, 'quota': quota_pk},
    )
    # Single-product quota: counts link to the filtered order list.
    assert f'href="{orders_url}?product={env["product"].pk}&amp;status=p"' in row  # paid
    assert f'href="{orders_url}?product={env["product"].pk}&amp;status=n"' in row  # pending
    assert f'href="{orders_url}?product={env["product"].pk}"' in row               # ordered
    # Quota name links to the quota detail page.
    assert f'href="{quota_url}"' in row


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_multi_product_quota_links_to_quota_detail(client, env):
    with scope(organizer=env['organizer'], event=env['event']):
        second = Product.objects.create(event=env['event'], name='Second', default_price=5, admission=True)
    _make_quota(env, 'Combo', 10, [env['product'], second])

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    sc = response.context['sales_capacity']
    row = next(r for r in sc['rows'] if r['name'] == 'Combo')
    with scope(organizer=env['organizer'], event=env['event']):
        quota_pk = env['event'].quotas.first().pk
    quota_url = reverse(
        'control:event.products.quotas.show',
        kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug, 'quota': quota_pk},
    )
    # Multi-product quota: counts fall back to the quota detail page.
    assert row['paid_url'] == quota_url
    assert row['ordered_url'] == quota_url


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_variation_product_names(client, env):
    # A product with variations is listed via its variations, not as a bare
    # product name. This exercises the variation_count path (no per-product
    # has_variations query).
    with scope(organizer=env['organizer'], event=env['event']):
        varprod = Product.objects.create(event=env['event'], name='Shirt', default_price=20, admission=True)
        v_s = varprod.variations.create(value='Small')
        v_l = varprod.variations.create(value='Large')
    with scope(organizer=env['organizer'], event=env['event']):
        q = env['event'].quotas.create(name='Shirts', size=10)
        q.variations.add(v_s, v_l)

    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    sc = response.context['sales_capacity']
    row = next(r for r in sc['rows'] if r['name'] == 'Shirts')
    # Variation entries are shown; the bare product name is not.
    assert any('Small' in name for name in row['products'])
    assert any('Large' in name for name in row['products'])
    assert 'Shirt' not in row['products']


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_subevent_filtering(client, env):
    with scopes_disabled():
        event = env['event']
        event.has_subevents = True
        event.save(update_fields=['has_subevents'])
    with scope(organizer=env['organizer'], event=env['event']):
        se1 = event.subevents.create(name='Day 1', date_from=now())
        se2 = event.subevents.create(name='Day 2', date_from=now())
        q1 = event.quotas.create(name='Q day1', size=10, subevent=se1)
        q1.products.add(env['product'])
        q2 = event.quotas.create(name='Q day2', size=10, subevent=se2)
        q2.products.add(env['product'])
        # Event-level quota (no date) applies to every date.
        qall = event.quotas.create(name='Q all dates', size=10, subevent=None)
        qall.products.add(env['product'])

    client.force_login(env['user_with_perm'])

    # No date selected -> every quota shown.
    sc_all = client.get(_dashboard_url(env)).context['sales_capacity']
    names_all = {r['name'] for r in sc_all['rows']}
    assert {'Q day1', 'Q day2', 'Q all dates'} <= names_all

    # se1 selected -> that date's quota AND the event-level quota, but not
    # another date's quota.
    sc1 = client.get(_dashboard_url(env, subevent=se1)).context['sales_capacity']
    names1 = {r['name'] for r in sc1['rows']}
    assert names1 == {'Q day1', 'Q all dates'}
    assert 'Q day2' not in names1

    # The date-specific quota's links carry the selected date; the event-level
    # quota's links must NOT (it counts null-subevent positions that a
    # date-filtered order list would exclude).
    day1_row = next(r for r in sc1['rows'] if r['name'] == 'Q day1')
    allrow = next(r for r in sc1['rows'] if r['name'] == 'Q all dates')
    assert f'subevent={se1.pk}' in day1_row['paid_url']
    # The event-level quota counts only null-subevent positions, which an order
    # list filtered by the selected date cannot express, so its counts link to
    # the quota detail instead (avoids a count-vs-destination mismatch).
    with scope(organizer=env['organizer'], event=event):
        qall_pk = event.quotas.get(name='Q all dates').pk
    quota_detail = reverse(
        'control:event.products.quotas.show',
        kwargs={'organizer': env['organizer'].slug, 'event': event.slug, 'quota': qall_pk},
    )
    assert allrow['paid_url'] == quota_detail
    assert allrow['ordered_url'] == quota_detail


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_hidden_without_order_permission(client, env):
    _make_quota(env, 'Main', 10, [env['product']])
    client.force_login(env['user_no_perm'])
    response = client.get(_dashboard_url(env))
    assert response.status_code == 200
    assert response.context['sales_capacity'] is None
    assert 'td-sales-title' not in response.content.decode()


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_empty_state(client, env):
    # No quotas at all -> section renders a placeholder, not an empty table.
    client.force_login(env['user_with_perm'])
    response = client.get(_dashboard_url(env))
    sc = response.context['sales_capacity']
    assert sc['has_quotas'] is False
    section = _sales_section(response.content.decode())
    assert 'No quotas have been set up yet.' in section
    assert '<table' not in section
