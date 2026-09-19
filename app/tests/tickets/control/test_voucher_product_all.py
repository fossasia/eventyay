import pytest
from bs4 import BeautifulSoup
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from django_scopes import scope

from eventyay.base.models import (
    Event,
    Organizer,
    Product,
    ProductVariation,
    Quota,
    Team,
    User,
    Voucher,
)
from eventyay.control.forms.vouchers import ALL_PRODUCTS, VoucherForm


@pytest.fixture
def env():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    event = Event.objects.create(organizer=organizer, name='Dummy', slug='dummy', date_from=now())
    user = User.objects.create_user('dummy@dummy.dummy', 'dummy')
    team = Team.objects.create(organizer=organizer, can_view_vouchers=True, can_change_vouchers=True)
    team.members.add(user)
    team.limit_events.add(event)
    with scope(organizer=organizer, event=event):
        product = Product.objects.create(event=event, name='Early-bird ticket', default_price=23)
        quota = Quota.objects.create(event=event, name='Tickets', size=5)
        quota.products.add(product)
    return organizer, event, user, product


def _label(doc, text):
    return next(span.parent for span in doc.select('label > .label-text') if span.get_text(strip=True) == text)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_voucher_detail_hides_optional_for_valid_until_and_product(client, env):
    organizer, event, user, product = env
    client.force_login(user)

    response = client.get(
        reverse('control:event.vouchers.add', kwargs={'organizer': organizer.slug, 'event': event.slug})
    )

    assert response.status_code == 200
    doc = BeautifulSoup(response.content.decode(), 'lxml')
    assert not _label(doc, 'Valid until').select('.optional')
    assert not _label(doc, 'Product').select('.optional')
    assert _label(doc, 'Comment').select('.optional')
    assert doc.select_one('.language-grid-widget[data-product-grid-widget]')
    selected = doc.select_one(f'input[name="productvar"][value="{ALL_PRODUCTS}"]')
    assert selected is not None
    assert selected.has_attr('checked')


@override_settings(DEBUG=True)
@pytest.mark.django_db
@pytest.mark.parametrize('query', ['', 'all', 'All prod'])
def test_product_select2_lists_all_products_option(client, env, query):
    organizer, event, user, product = env
    client.force_login(user)

    response = client.get(
        reverse(
            'control:event.vouchers.productselect2',
            kwargs={'organizer': organizer.slug, 'event': event.slug},
        ),
        {'query': query},
    )

    assert response.status_code == 200
    results = response.json()['results']
    assert results[0]['id'] == ALL_PRODUCTS
    assert results[0]['text'] == 'All products'


@override_settings(DEBUG=True)
@pytest.mark.django_db
@pytest.mark.parametrize('query', ['Early', 'duct', 'pro'])
def test_product_select2_omits_all_products_for_unrelated_query(client, env, query):
    organizer, event, user, product = env
    client.force_login(user)

    response = client.get(
        reverse(
            'control:event.vouchers.productselect2',
            kwargs={'organizer': organizer.slug, 'event': event.slug},
        ),
        {'query': query},
    )

    assert response.status_code == 200
    assert ALL_PRODUCTS not in [r['id'] for r in response.json()['results']]


@pytest.mark.django_db
def test_voucher_form_all_products_clears_product_and_quota(env):
    organizer, event, user, product = env
    with scope(organizer=organizer, event=event):
        voucher = Voucher.objects.create(event=event, product=product)
        form = VoucherForm(
            instance=voucher,
            data={
                'code': voucher.code,
                'max_usages': '1',
                'price_mode': 'none',
                'productvar': [ALL_PRODUCTS],
            },
        )

        assert form.is_valid(), form.errors
        form.save()
        voucher.refresh_from_db()

    assert voucher.product is None
    assert voucher.variation is None
    assert voucher.quota is None
    assert voucher.limit_products.count() == 0
    assert voucher.limit_variations.count() == 0


@pytest.mark.django_db
def test_voucher_form_multi_product_selection(env):
    organizer, event, user, product = env
    with scope(organizer=organizer, event=event):
        product_b = Product.objects.create(event=event, name='Regular ticket', default_price=42)
        voucher = Voucher.objects.create(event=event)
        form = VoucherForm(
            instance=voucher,
            data={
                'code': voucher.code,
                'max_usages': '1',
                'price_mode': 'none',
                'productvar': [str(product.pk), str(product_b.pk)],
            },
        )

        assert form.is_valid(), form.errors
        form.save()
        voucher.refresh_from_db()

        assert voucher.product is None
        assert voucher.quota is None
        assert set(voucher.limit_products.values_list('pk', flat=True)) == {product.pk, product_b.pk}
        assert voucher.applies_to(product)
        assert voucher.applies_to(product_b)

        other = Product.objects.create(event=event, name='Other', default_price=10)
        assert not voucher.applies_to(other)


@pytest.mark.django_db
def test_voucher_form_drops_variations_covered_by_product_wide(env):
    organizer, event, user, product = env
    with scope(organizer=organizer, event=event):
        product_with_vars = Product.objects.create(event=event, name='Shirt', default_price=12)
        red = ProductVariation.objects.create(product=product_with_vars, value='Red', default_price=12)
        ProductVariation.objects.create(product=product_with_vars, value='Blue', default_price=12)
        voucher = Voucher.objects.create(event=event)
        form = VoucherForm(
            instance=voucher,
            data={
                'code': voucher.code,
                'max_usages': '1',
                'price_mode': 'none',
                'productvar': [str(product_with_vars.pk), f'{product_with_vars.pk}-{red.pk}', str(product.pk)],
            },
        )

        assert form.is_valid(), form.errors
        form.save()
        voucher.refresh_from_db()

        assert set(voucher.limit_products.values_list('pk', flat=True)) == {
            product.pk,
            product_with_vars.pk,
        }
        assert voucher.limit_variations.count() == 0
        assert voucher.applies_to(product_with_vars, red)


@pytest.mark.django_db
def test_voucher_form_copy_initial_keeps_selected_products_in_choices(env):
    organizer, event, user, product = env
    with scope(organizer=organizer, event=event):
        voucher = Voucher(event=event)
        form = VoucherForm(
            instance=voucher,
            initial={'productvar': [str(product.pk)]},
        )
        choice_ids = {value for value, _label in form.fields['productvar'].choices}
        assert str(product.pk) in choice_ids
