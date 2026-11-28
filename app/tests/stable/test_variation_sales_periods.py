import datetime
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import (
    CartPosition,
    Product,
    ProductBundle,
    ProductCategory,
    ProductVariation,
    Quota,
)
from eventyay.base.services.cart import CartError, CartManager


@dataclass
class VariationCartSetup:
    shirt: Product
    shirt_red: ProductVariation
    shirt_blue: ProductVariation
    ticket: Product


def _extract_form_fields(form):
    data = {}
    for field in form.find_all('input'):
        field_type = field.get('type', 'text')
        if field_type in ('submit', 'image') and not field.has_attr('name'):
            continue

        if field_type in ('checkbox', 'radio'):
            if field.has_attr('checked') and field.has_attr('name'):
                name = field['name']
                value = field.get('value', 'on')
                if name in data:
                    if not isinstance(data[name], list):
                        data[name] = [data[name]]
                    data[name].append(value)
                else:
                    data[name] = value
        elif field.has_attr('name'):
            name = field['name']
            value = field.get('value', '')
            if name in data:
                if not isinstance(data[name], list):
                    data[name] = [data[name]]
                data[name].append(value)
            else:
                data[name] = value

    for textarea in form.find_all('textarea'):
        if not textarea.has_attr('name'):
            continue
        name = textarea['name']
        value = textarea.text or ''
        if name in data:
            if not isinstance(data[name], list):
                data[name] = [data[name]]
            data[name].append(value)
        else:
            data[name] = value

    for select in form.find_all('select'):
        if not select.has_attr('name'):
            continue
        name = select['name']
        options = select.find_all('option')
        is_multiple = select.has_attr('multiple')
        selected_options = [option for option in options if option.has_attr('selected')]
        if not selected_options and options and not is_multiple:
            selected_options = [options[0]]

        if is_multiple:
            value = [option['value'] for option in selected_options]
        elif len(selected_options) == 1:
            value = selected_options[0]['value']
        else:
            value = ''

        if name in data:
            if not isinstance(data[name], list):
                data[name] = [data[name]]
            data[name].append(value)
        else:
            data[name] = value

    return data


@pytest.fixture
def variation_cart_setup(event, settings) -> VariationCartSetup:
    settings.SITE_URL = 'https://testserver'
    settings.SITE_NETLOC = 'testserver'
    settings.CELERY_TASK_ALWAYS_EAGER = True
    event.tickets_published = True
    event.sales_channels = ['web', 'bar']
    event.save(update_fields=['tickets_published', 'sales_channels'])
    event.settings.set('require_registered_account_for_tickets', False)
    event.settings.set('redirect_to_checkout_directly', False)

    with scope(organizer=event.organizer, event=event):
        tr19 = event.tax_rules.create(rate=Decimal('19.00'))
        category = ProductCategory.objects.create(event=event, name='Everything', position=0)
        quota_shirts = Quota.objects.create(event=event, name='Shirts', size=2)
        shirt = Product.objects.create(
            event=event,
            name='T-Shirt',
            category=category,
            default_price=Decimal('12.00'),
            tax_rule=tr19,
        )
        quota_shirts.products.add(shirt)
        shirt_red = ProductVariation.objects.create(product=shirt, default_price=Decimal('14.00'), value='Red')
        shirt_blue = ProductVariation.objects.create(product=shirt, value='Blue')
        quota_shirts.variations.add(shirt_red, shirt_blue)

        quota_tickets = Quota.objects.create(event=event, name='Tickets', size=5)
        ticket = Product.objects.create(
            event=event,
            name='Early-bird ticket',
            category=category,
            default_price=Decimal('23.00'),
            tax_rule=tr19,
        )
        quota_tickets.products.add(ticket)

        quota_all = Quota.objects.create(event=event, name='All', size=None)
        quota_all.products.add(ticket, shirt)
        quota_all.variations.add(shirt_blue, shirt_red)

    return VariationCartSetup(
        shirt=shirt,
        shirt_red=shirt_red,
        shirt_blue=shirt_blue,
        ticket=ticket,
    )


@pytest.mark.django_db
def test_variation_is_available(event):
    with scope(organizer=event.organizer, event=event):
        product = Product.objects.create(event=event, name='Ticket', default_price=23, active=True)
        variation = ProductVariation.objects.create(product=product, value='Early Bird', active=True)
        assert variation.is_available()

        variation.available_from = now() - timedelta(days=1)
        variation.available_until = now() + timedelta(days=1)
        assert variation.is_available()

        variation.available_from = now() + timedelta(days=1)
        variation.available_until = None
        assert not variation.is_available()

        variation.available_from = None
        variation.available_until = now() - timedelta(days=1)
        assert not variation.is_available()

        variation.available_until = None
        variation.active = False
        assert not variation.is_available()


@pytest.mark.django_db
def test_variation_sellout_opens_next_early(event):
    with scope(organizer=event.organizer, event=event):
        product = Product.objects.create(
            event=event,
            name='Ticket',
            default_price=23,
            active=True,
            start_next_variation_on_sellout=True,
        )
        early = ProductVariation.objects.create(product=product, value='Early Bird', active=True, position=0)
        regular = ProductVariation.objects.create(
            product=product,
            value='Regular',
            active=True,
            position=1,
            available_from=now() + timedelta(days=7),
        )
        q_early = Quota.objects.create(event=event, name='Early', size=0)
        q_early.products.add(product)
        q_early.variations.add(early)
        q_regular = Quota.objects.create(event=event, name='Regular', size=10)
        q_regular.products.add(product)
        q_regular.variations.add(regular)

        assert early.check_quotas()[0] < Quota.AVAILABILITY_RESERVED
        assert regular.is_available()

        product.start_next_variation_on_sellout = False
        product.save()
        assert not regular.is_available()


@pytest.mark.django_db
def test_update_variation_sales_period(organizer_client, organizer, event, settings):
    settings.SITE_URL = 'https://testserver'
    settings.SITE_NETLOC = 'testserver'
    with scope(organizer=organizer, event=event):
        product = Product.objects.create(
            event=event,
            name='Business',
            default_price=0,
            active=True,
            admission=True,
        )
        var1 = ProductVariation.objects.create(product=product, value='Silver')
        var2 = ProductVariation.objects.create(product=product, value='Gold')

    url = reverse(
        'control:event.product',
        kwargs={'organizer': organizer.slug, 'event': event.slug, 'product': product.id},
    )
    get_resp = organizer_client.get(url, secure=True)
    assert get_resp.status_code == 200
    doc = BeautifulSoup(get_resp.content, 'lxml')
    assert 'Available from' in doc.text
    assert 'Check-in validity' in doc.text
    assert 'Edit check-in settings' in doc.text

    data = _extract_form_fields(doc.select_one('form.form-horizontal'))
    data.update(
        {
            'variations-TOTAL_FORMS': '2',
            'variations-INITIAL_FORMS': '2',
            'variations-MIN_NUM_FORMS': '0',
            'variations-MAX_NUM_FORMS': '1000',
            'variations-0-id': str(var1.pk),
            'variations-0-value_0': 'Bronze',
            'variations-0-active': 'yes',
            'variations-0-available_until_0': '2026-12-15',
            'variations-0-available_until_1': '23:59:00',
            'variations-1-id': str(var2.pk),
            'variations-1-value_0': 'Gold',
            'variations-1-active': 'yes',
            'start_next_variation_on_sellout': 'on',
            'admission': 'on',
        }
    )
    post_resp = organizer_client.post(url, data, secure=True)
    assert post_resp.status_code == 302

    with scope(organizer=organizer, event=event):
        var1.refresh_from_db()
        product.refresh_from_db()
        assert str(var1.value) == 'Bronze'
        assert var1.available_until is not None
        assert var1.available_until.astimezone(ZoneInfo(event.settings.timezone)).date() == datetime.date(2026, 12, 15)
        assert product.start_next_variation_on_sellout


@pytest.mark.django_db
def test_add_variation_with_existing_does_not_recurse(organizer_client, organizer, event, settings):
    """Regression: constructing a new variation must not read self.forms."""
    settings.SITE_URL = 'https://testserver'
    settings.SITE_NETLOC = 'testserver'
    with scope(organizer=organizer, event=event):
        product = Product.objects.create(
            event=event,
            name='Business',
            default_price=0,
            active=True,
            admission=True,
        )
        var1 = ProductVariation.objects.create(product=product, value='Silver')
        var2 = ProductVariation.objects.create(product=product, value='Gold')

    url = reverse(
        'control:event.product',
        kwargs={'organizer': organizer.slug, 'event': event.slug, 'product': product.id},
    )
    get_resp = organizer_client.get(url, secure=True)
    assert get_resp.status_code == 200
    doc = BeautifulSoup(get_resp.content, 'lxml')
    data = _extract_form_fields(doc.select_one('form.form-horizontal'))
    data.update(
        {
            'variations-TOTAL_FORMS': '3',
            'variations-INITIAL_FORMS': '2',
            'variations-MIN_NUM_FORMS': '0',
            'variations-MAX_NUM_FORMS': '1000',
            'variations-0-id': str(var1.pk),
            'variations-0-value_0': 'Silver',
            'variations-0-active': 'yes',
            'variations-1-id': str(var2.pk),
            'variations-1-value_0': 'Gold',
            'variations-1-active': 'yes',
            'variations-2-id': '',
            'variations-2-value_0': 'Platinum',
            'variations-2-active': 'yes',
            'admission': 'on',
        }
    )
    response = organizer_client.post(url, data, secure=True)
    assert response.status_code == 302
    with scope(organizer=organizer, event=event):
        assert product.variations.count() == 3
        assert any(str(v.value) == 'Platinum' for v in product.variations.all())


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('from_delta', 'until_delta'),
    [
        (timedelta(days=-2), timedelta(days=2)),
        (timedelta(days=-2), None),
        (None, timedelta(days=2)),
    ],
)
def test_variation_in_time_available(client, event, variation_cart_setup, from_delta, until_delta):
    with scope(organizer=event.organizer, event=event):
        variation_cart_setup.shirt_red.available_from = now() + from_delta if from_delta else None
        variation_cart_setup.shirt_red.available_until = now() + until_delta if until_delta else None
        variation_cart_setup.shirt_red.save()

    client.get(f'/{event.organizer.slug}/{event.slug}/', secure=True)
    client.post(
        f'/{event.organizer.slug}/{event.slug}/cart/add',
        {f'variation_{variation_cart_setup.shirt.id}_{variation_cart_setup.shirt_red.id}': '1'},
        follow=True,
        secure=True,
    )
    cart_id = client.session.get(f'current_cart_event_{event.pk}')
    with scope(organizer=event.organizer, event=event):
        assert CartPosition.objects.filter(cart_id=cart_id, event=event).count() == 1


@pytest.mark.django_db
def test_variation_no_longer_available(client, event, variation_cart_setup):
    with scope(organizer=event.organizer, event=event):
        variation_cart_setup.shirt_red.available_until = now() - timedelta(days=2)
        variation_cart_setup.shirt_red.save()

    client.get(f'/{event.organizer.slug}/{event.slug}/', secure=True)
    client.post(
        f'/{event.organizer.slug}/{event.slug}/cart/add',
        {f'variation_{variation_cart_setup.shirt.id}_{variation_cart_setup.shirt_red.id}': '1'},
        follow=True,
        secure=True,
    )
    with scope(organizer=event.organizer, event=event):
        assert CartPosition.objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_variation_not_yet_available(client, event, variation_cart_setup):
    with scope(organizer=event.organizer, event=event):
        variation_cart_setup.shirt_red.available_from = now() + timedelta(days=2)
        variation_cart_setup.shirt_red.save()

    client.get(f'/{event.organizer.slug}/{event.slug}/', secure=True)
    client.post(
        f'/{event.organizer.slug}/{event.slug}/cart/add',
        {f'variation_{variation_cart_setup.shirt.id}_{variation_cart_setup.shirt_red.id}': '1'},
        follow=True,
        secure=True,
    )
    with scope(organizer=event.organizer, event=event):
        assert CartPosition.objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_extend_expired_removes_unavailable_variation(event, variation_cart_setup):
    """Expired cart lines past variation available_until are removed, not aborting commit."""
    cart_id = 'test-cart-expired-variation'
    with scope(organizer=event.organizer, event=event):
        variation_cart_setup.shirt_red.available_until = now() - timedelta(days=2)
        variation_cart_setup.shirt_red.save()
        CartPosition.objects.create(
            expires=now() - timedelta(minutes=10),
            product=variation_cart_setup.shirt,
            variation=variation_cart_setup.shirt_red,
            price=Decimal('14.00'),
            event=event,
            cart_id=cart_id,
        )
        ticket_cp = CartPosition.objects.create(
            expires=now() - timedelta(minutes=10),
            product=variation_cart_setup.ticket,
            price=Decimal('23.00'),
            event=event,
            cart_id=cart_id,
        )
        cm = CartManager(event=event, cart_id=cart_id)
        try:
            cm.commit()
        except CartError:
            pass
        assert not CartPosition.objects.filter(
            cart_id=cart_id,
            variation=variation_cart_setup.shirt_red,
        ).exists()
        ticket_cp.refresh_from_db()
        assert ticket_cp.expires > now()


@pytest.mark.django_db
def test_extend_expired_removes_bundle_when_child_unavailable(event, variation_cart_setup):
    """Unavailable bundled child must drop the whole expired bundle, not renew the parent alone."""
    cart_id = 'test-cart-expired-bundle'
    with scope(organizer=event.organizer, event=event):
        trans = Product.objects.create(
            event=event,
            name='Public Transport Ticket',
            default_price=Decimal('2.50'),
            require_bundling=True,
            available_until=now() - timedelta(days=2),
        )
        trans_quota = Quota.objects.create(event=event, name='Transport', size=5)
        trans_quota.products.add(trans)
        ProductBundle.objects.create(
            base_product=variation_cart_setup.ticket,
            bundled_product=trans,
            designated_price=Decimal('1.50'),
            count=1,
        )
        cp = CartPosition.objects.create(
            expires=now() - timedelta(minutes=10),
            product=variation_cart_setup.ticket,
            price=Decimal('21.50'),
            event=event,
            cart_id=cart_id,
        )
        CartPosition.objects.create(
            expires=now() - timedelta(minutes=10),
            product=trans,
            price=Decimal('1.50'),
            event=event,
            cart_id=cart_id,
            addon_to=cp,
            is_bundled=True,
        )
        cm = CartManager(event=event, cart_id=cart_id)
        try:
            cm.commit()
        except CartError:
            pass
        assert not CartPosition.objects.filter(cart_id=cart_id, event=event).exists()


@pytest.mark.django_db
def test_ticket_page_shows_compact_upcoming_and_buyable_variants(client, event, variation_cart_setup):
    """Upcoming variants appear without a quantity field; buyable ones keep one."""
    with scope(organizer=event.organizer, event=event):
        variation_cart_setup.shirt_red.available_from = now() - timedelta(days=1)
        variation_cart_setup.shirt_red.available_until = now() + timedelta(days=5)
        variation_cart_setup.shirt_red.description = 'Buyable red shirt details'
        variation_cart_setup.shirt_red.save()
        variation_cart_setup.shirt_blue.available_from = now() + timedelta(days=6)
        variation_cart_setup.shirt_blue.available_until = None
        variation_cart_setup.shirt_blue.description = 'Upcoming blue shirt should stay hidden'
        variation_cart_setup.shirt_blue.save()
        red_id = variation_cart_setup.shirt_red.id
        blue_id = variation_cart_setup.shirt_blue.id
        shirt_id = variation_cart_setup.shirt.id

    response = client.get(f'/{event.organizer.slug}/{event.slug}/', secure=True)
    assert response.status_code == 200
    html = response.content.decode()
    assert f'name="variation_{shirt_id}_{red_id}"' in html
    assert f'name="variation_{shirt_id}_{blue_id}"' not in html
    assert 'variation-upcoming' in html
    assert 'variation-compact' in html
    assert 'variation-sales-date--active' in html
    assert 'input-product-count--compact' in html
    assert 'variation-toggle' in html
    assert 'Buyable red shirt details' in html
    assert 'Upcoming blue shirt should stay hidden' not in html


@pytest.mark.django_db
def test_ticket_page_headline_price_ignores_expired_phases(client, event, variation_cart_setup):
    """Headline min/max uses buyable phases only, not historical expired prices."""
    with scope(organizer=event.organizer, event=event):
        variation_cart_setup.shirt_red.default_price = Decimal('50.00')
        variation_cart_setup.shirt_red.available_from = now() - timedelta(days=1)
        variation_cart_setup.shirt_red.available_until = now() + timedelta(days=5)
        variation_cart_setup.shirt_red.save()
        variation_cart_setup.shirt_blue.default_price = Decimal('10.00')
        variation_cart_setup.shirt_blue.available_from = None
        variation_cart_setup.shirt_blue.available_until = now() - timedelta(days=1)
        variation_cart_setup.shirt_blue.save()

    response = client.get(f'/{event.organizer.slug}/{event.slug}/', secure=True)
    assert response.status_code == 200
    soup = BeautifulSoup(response.content, 'html.parser')
    shirt_article = soup.select_one(f'#item-{variation_cart_setup.shirt.id}')
    assert shirt_article is not None
    headline_price = shirt_article.select_one('summary .price, .headline .price')
    assert headline_price is not None
    price_text = ' '.join(headline_price.stripped_strings)
    assert '50.00' in price_text
    assert '10.00' not in price_text
