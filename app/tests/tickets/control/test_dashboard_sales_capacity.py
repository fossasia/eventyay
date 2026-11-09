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
    # Event-owned data is created under the tenant scope.
    with scope(organizer=organizer, event=event):
        product = Product.objects.create(event=event, name='Ticket', default_price=25, admission=True, active=True)
    return {'organizer': organizer, 'event': event, 'user': user, 'product': product}


def _url(env, name='control:event.index', **kwargs):
    return reverse(name, kwargs={'organizer': env['organizer'].slug, 'event': env['event'].slug, **kwargs})


def _get(client, env, subevent=None):
    client.force_login(env['user'])
    url = _url(env) + (f'?subevent={subevent.pk}' if subevent else '')
    response = client.get(url)
    assert response.status_code == 200
    return response


def _section(response):
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


def _order(env, status, product, n=1, variation=None, subevent=None, canceled=0):
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
        _order(env, Order.STATUS_PAID, env['product'], n=paid)
    if pending:
        _order(env, Order.STATUS_PENDING, env['product'], n=pending)

    response = _get(client, env)
    row = _row(response, 'Main')
    assert (row['paid'], row['pending'], row['ordered']) == (paid, pending, paid + pending)
    assert row['capacity'] == size
    assert row['remaining'] == remaining
    assert row['status_key'] == status_key
    if size is None:
        assert '&infin;' in _section(response)


@pytest.mark.django_db
@override_settings(SITE_URL='https://testserver')
def test_sales_totals_count_distinct_active_positions(client, env):
    # The same product in two quotas, plus a canceled ticket in a paid order.
    _quota(env, 'All event', 100, [env['product']])
    _quota(env, 'VIP block', 10, [env['product']])
    _order(env, Order.STATUS_PAID, env['product'], n=3, canceled=1)
    _order(env, Order.STATUS_PENDING, env['product'], n=1)
    # A quota limited to one variation must not count the product's others.
    with scope(organizer=env['organizer'], event=env['event']):
        shirt = Product.objects.create(event=env['event'], name='Shirt', default_price=20, admission=True)
        small = shirt.variations.create(value='Small')
        large = shirt.variations.create(value='Large')
    _quota(env, 'Small shirts', 10, [shirt], [small])
    _order(env, Order.STATUS_PAID, shirt, variation=small)
    _order(env, Order.STATUS_PAID, shirt, variation=large)

    response = _get(client, env)
    # Each row shows its own full count...
    assert _row(response, 'All event')['paid'] == 3
    assert _row(response, 'VIP block')['paid'] == 3
    # ...but totals count each active position once: 3 tickets + 1 Small shirt.
    totals = response.context['sales_capacity']['totals']
    assert (totals['paid'], totals['pending'], totals['ordered']) == (4, 1, 5)
    # Capacity and remaining cannot be summed across overlapping quotas.
    tfoot = re.search(r'<tfoot>(.*?)</tfoot>', _section(response), re.DOTALL).group(1)
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
    _order(env, Order.STATUS_PAID, env['product'], subevent=se1)
    # A workshop with a quota on Day 1 only, sold on Day 2: no row counts it.
    with scope(organizer=env['organizer'], event=event):
        workshop = Product.objects.create(event=event, name='Workshop', default_price=10, admission=True)
    _quota(env, 'Workshop day1', 10, [workshop], subevent=se1)
    _order(env, Order.STATUS_PAID, workshop, subevent=se2)

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
    section = _section(response)
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
    assert _url(env, 'control:event.products.quotas.show', quota=main.pk) not in _section(response)

    # Cannot view orders: the section is not rendered.
    client.force_login(no_orders)
    response = client.get(_url(env))
    assert response.status_code == 200
    assert response.context['sales_capacity'] is None
    assert 'td-sales-title' not in response.content.decode()
