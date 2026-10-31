import re

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, Order, Organizer, Product, Question, Quota, Team, User


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
        user = User.objects.create_user('orga@example.com', 'dummy')
        team = Team.objects.create(
            organizer=organizer,
            can_view_orders=True,
            can_view_vouchers=True,
            can_change_items=True,
            all_events=True,
        )
        team.members.add(user)
    with scope(organizer=organizer, event=event):
        product = Product.objects.create(event=event, name='Early bird ticket', default_price=10, admission=True)
        shirt = Product.objects.create(event=event, name='Shirt', default_price=20)
        shirt.variations.create(value='Large')
        quota = Quota.objects.create(event=event, name='Main quota', size=10)
        quota.products.add(product)
        checkin_list = event.checkin_lists.create(name='Default', all_products=True)
        shirt_list = event.checkin_lists.create(name='Merchandise', all_products=False)
        shirt_list.limit_products.add(shirt)
        question = Question.objects.create(event=event, question='Dietary requirements', type=Question.TYPE_STRING)
        question.products.add(product)
        # The orders page only shows its filters once the event has an order.
        Order.objects.create(
            event=event, status=Order.STATUS_PAID, datetime=now(), expires=now(), total=10, code='FLT01'
        )
    return {
        'organizer': organizer,
        'event': event,
        'product': product,
        'shirt': shirt,
        'quota': quota,
        'checkin_list': checkin_list,
        'shirt_list': shirt_list,
        'question': question,
        'user': user,
    }


def _url(env, name, **extra):
    kwargs = {'organizer': env['organizer'].slug, 'event': env['event'].slug, **extra}
    return reverse(name, kwargs=kwargs)


def _pages(env):
    """(url, name of the product filter field) for every page with a product filter."""
    return [
        (_url(env, 'control:event.orders'), 'product'),
        (_url(env, 'control:event.orders.search'), 'expert-product'),
        (_url(env, 'control:event.vouchers'), 'productvar'),
        (_url(env, 'control:event.orders.checkinlists.show', list=env['checkin_list'].pk), 'product'),
        (_url(env, 'control:event.orders.waitinglist'), 'product'),
        (_url(env, 'control:event.products.questions.show', question=env['question'].pk), 'product'),
    ]


def _product_select(content, field):
    match = re.search(rf'<select[^>]*name="{field}"[^>]*>(.*?)</select>', content, re.S)
    assert match, f'no <select name="{field}">'
    return match.group(0)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_product_filters_are_searchable(client, env):
    client.force_login(env['user'])
    for url, field in _pages(env):
        response = client.get(url)
        assert response.status_code == 200, url
        content = response.content.decode()
        select = _product_select(content, field)
        opening_tag = select.split('>', 1)[0]
        assert 'data-searchable-select' in opening_tag, url
        assert 'data-all-label="All products"' in opening_tag, url
        assert 'data-search-placeholder="Search"' in opening_tag, url
        assert 'data-empty-text="No results"' in opening_tag, url
        assert 'Early bird ticket' in select, url
        assert 'common/js/searchable-select.js' in content, url
        assert 'common/css/searchable-select.css' in content, url


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_product_filters_keep_variations_and_quota_options(client, env):
    client.force_login(env['user'])
    orders = _product_select(client.get(_url(env, 'control:event.orders')).content.decode(), 'product')
    assert 'Shirt – Any variation' in orders
    assert 'Shirt – Large' in orders

    vouchers = _product_select(client.get(_url(env, 'control:event.vouchers')).content.decode(), 'productvar')
    assert 'Shirt – Large' in vouchers
    assert f'value="q-{env["quota"].pk}"' in vouchers


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_checkin_list_filter_only_lists_its_products(client, env):
    client.force_login(env['user'])
    url = _url(env, 'control:event.orders.checkinlists.show', list=env['shirt_list'].pk)
    select = _product_select(client.get(url).content.decode(), 'product')
    assert 'data-searchable-select' in select
    assert 'Shirt' in select
    assert 'Early bird ticket' not in select


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_product_filters_still_filter(client, env):
    client.force_login(env['user'])
    product_pk = env['product'].pk
    for url, field in _pages(env):
        response = client.get(url, {field: product_pk})
        assert response.status_code == 200, url
        select = _product_select(response.content.decode(), field)
        assert re.search(rf'<option value="{product_pk}"\s+selected', select), url
