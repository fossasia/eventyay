import csv
import json
from decimal import Decimal
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.timezone import now
from django_scopes import scopes_disabled
from i18nfield.strings import LazyI18nString

from eventyay.base.models import (
    CachedFile,
    Event,
    OrderPosition,
    Organizer,
    Product,
    User,
)
from eventyay.base.orderimport import ProductColumn, get_product_import_preview
from eventyay.base.services.orderimport import DataImportError, import_orders


@pytest.fixture
def event():
    organizer = Organizer.objects.create(name='Dummy', slug='dummy')
    return Event.objects.create(
        organizer=organizer,
        name='Dummy',
        slug='dummy',
        date_from=now(),
        plugins='pretix.plugins.banktransfer',
    )


@pytest.fixture
def user():
    return User.objects.create_user('test@localhost', 'test')


def make_import_settings(**overrides):
    settings = {
        'orders': 'many',
        'testmode': False,
        'status': 'paid',
        'create_missing_products': False,
        'email': 'csv:Email',
        'product': 'csv:Product',
        'variation': 'empty',
        'price': 'csv:Price',
        'invoice_address_company': 'empty',
        'invoice_address_name_full_name': 'empty',
        'invoice_address_street': 'empty',
        'invoice_address_zipcode': 'empty',
        'invoice_address_city': 'empty',
        'invoice_address_country': 'static:DE',
        'invoice_address_state': 'empty',
        'invoice_address_vat_id': 'empty',
        'invoice_address_internal_reference': 'empty',
        'attendee_name_full_name': 'empty',
        'attendee_email': 'empty',
        'secret': 'empty',
        'locale': 'static:en',
        'sales_channel': 'static:web',
        'comment': 'empty',
    }
    settings.update(overrides)
    return settings


def make_csv_file(rows):
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=['Email', 'Product', 'Price'], dialect=csv.excel)
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    cached = CachedFile.objects.create(type='text/csv', filename='input.csv')
    cached.file.save('input.csv', ContentFile(buffer.read()))
    return cached


@pytest.mark.django_db
@scopes_disabled()
def test_import_creates_missing_products_when_enabled(event, user):
    assert event.products.count() == 0

    cached = make_csv_file(
        [
            {'Email': 'a@example.com', 'Product': 'VIP', 'Price': '0.00'},
            {'Email': 'b@example.com', 'Product': 'Standard', 'Price': '0.00'},
            {'Email': 'c@example.com', 'Product': 'VIP', 'Price': '0.00'},
        ]
    )
    settings = make_import_settings(create_missing_products=True)

    import_orders.apply(args=(event.pk, cached.id, settings, 'en', user.pk)).get()

    products = list(event.products.all())
    assert len(products) == 2
    assert all(p.default_price == Decimal('0.00') for p in products)
    assert all(p.admission is True for p in products)
    product_names = {str(p) for p in products}
    assert product_names == {'VIP', 'Standard'}
    for product in products:
        quotas = list(product.quotas.all())
        assert len(quotas) == 1
        assert quotas[0].size is None
    assert event.orders.count() == 3
    assert OrderPosition.objects.count() == 3


@pytest.mark.django_db
@scopes_disabled()
def test_import_unknown_product_fails_without_create_missing(event, user):
    cached = make_csv_file([{'Email': 'a@example.com', 'Product': 'VIP', 'Price': '0.00'}])
    settings = make_import_settings(create_missing_products=False)

    with pytest.raises(DataImportError) as excinfo:
        import_orders.apply(args=(event.pk, cached.id, settings, 'en', user.pk)).get()

    assert 'No matching product was found.' in str(excinfo.value)
    assert event.products.count() == 0
    assert event.orders.count() == 0


@pytest.mark.django_db
@scopes_disabled()
def test_import_reuses_existing_product_and_creates_only_missing(event, user):
    existing = Product.objects.create(
        event=event,
        name=LazyI18nString('VIP'),
        default_price=Decimal('10.00'),
        admission=True,
    )
    cached = make_csv_file(
        [
            {'Email': 'a@example.com', 'Product': 'VIP', 'Price': '0.00'},
            {'Email': 'b@example.com', 'Product': 'Standard', 'Price': '0.00'},
        ]
    )
    settings = make_import_settings(create_missing_products=True)

    import_orders.apply(args=(event.pk, cached.id, settings, 'en', user.pk)).get()

    assert event.products.count() == 2
    assert OrderPosition.objects.filter(product=existing).count() == 1
    new_product = event.products.exclude(pk=existing.pk).get()
    assert str(new_product) == 'Standard'
    assert OrderPosition.objects.filter(product=new_product).count() == 1
    new_quota = new_product.quotas.get()
    assert new_quota.size is None


@pytest.mark.django_db
@scopes_disabled()
def test_product_import_preview_matched_and_create(event):
    Product.objects.create(
        event=event,
        name=LazyI18nString('VIP'),
        default_price=Decimal('10.00'),
    )
    records = [
        {'Email': 'a@example.com', 'Product': 'VIP', 'Price': '0.00'},
        {'Email': 'b@example.com', 'Product': 'Workshop', 'Price': '0.00'},
    ]
    settings = make_import_settings(create_missing_products=True, product='csv:Product')

    preview = get_product_import_preview(
        event, settings, fieldnames=['Email', 'Product', 'Price'], records=records
    )

    assert preview['unmapped'] is False
    assert len(preview['matched']) == 1
    assert preview['matched'][0]['csv_value'] == 'VIP'
    assert len(preview['to_create']) == 1
    assert preview['to_create'][0]['csv_value'] == 'Workshop'


@pytest.mark.django_db
@scopes_disabled()
def test_product_import_preview_missing_without_create(event):
    records = [{'Email': 'a@example.com', 'Product': 'New Ticket', 'Price': '0.00'}]
    settings = make_import_settings(create_missing_products=False, product='csv:Product')

    preview = get_product_import_preview(
        event, settings, fieldnames=['Email', 'Product', 'Price'], records=records
    )

    assert len(preview['missing']) == 1
    assert preview['missing'][0]['csv_value'] == 'New Ticket'
    assert preview['to_create'] == []


@pytest.mark.django_db
@scopes_disabled()
def test_product_import_preview_by_mapping_is_json_serializable(event):
    Product.objects.create(
        event=event,
        name=LazyI18nString('VIP'),
        default_price=Decimal('10.00'),
    )
    records = [
        {'Email': 'a@example.com', 'Product': 'VIP', 'Price': '0.00'},
        {'Email': 'b@example.com', 'Product': 'Workshop', 'Price': '0.00'},
    ]
    settings = make_import_settings(create_missing_products=True, product='csv:Product')

    preview = get_product_import_preview(
        event, settings, fieldnames=['Email', 'Product', 'Price'], records=records
    )

    json.dumps(preview['by_mapping'])
    assert 'csv:Product' in preview['by_mapping']
    assert f'static:{event.products.get().pk}' not in preview['by_mapping']


@pytest.mark.django_db
@scopes_disabled()
def test_product_import_preview_static_mapping(event):
    product = Product.objects.create(
        event=event,
        name=LazyI18nString('VIP'),
        default_price=Decimal('10.00'),
    )
    settings = make_import_settings(product=f'static:{product.pk}')

    preview = get_product_import_preview(event, settings, record_count=5)

    assert preview['unmapped'] is False
    assert len(preview['matched']) == 1
    assert preview['matched'][0]['rows'] == 5
    assert preview['matched'][0]['product_id'] == product.pk


@pytest.mark.django_db
@scopes_disabled()
def test_materialize_pending_products_raises_on_ambiguous(event):
    column = ProductColumn(event, create_missing=True)
    column._pending_product_names.add('VIP')
    Product.objects.create(
        event=event,
        name=LazyI18nString('VIP'),
        default_price=Decimal('0.00'),
        admission=True,
    )
    Product.objects.create(
        event=event,
        name=LazyI18nString('VIP'),
        default_price=Decimal('0.00'),
        admission=True,
    )

    with pytest.raises(ValidationError, match='Multiple matching products'):
        column.materialize_pending_products()


@pytest.mark.django_db
@scopes_disabled()
def test_materialize_pending_products_uses_current_db_state(event):
    column = ProductColumn(event, create_missing=True)
    column._pending_product_names.add('VIP')
    Product.objects.create(
        event=event,
        name=LazyI18nString('VIP'),
        default_price=Decimal('0.00'),
        admission=True,
    )

    created = column.materialize_pending_products()

    assert event.products.count() == 1
    product = event.products.get()
    assert created['VIP'].pk == product.pk
    quota = product.quotas.get()
    assert quota.size is None
    assert quota.name == 'VIP'


@pytest.mark.django_db
@scopes_disabled()
def test_import_validation_failure_does_not_create_products(event, user):
    cached = make_csv_file(
        [
            {'Email': 'valid@example.com', 'Product': 'New Product', 'Price': '0.00'},
            {'Email': 'not-an-email', 'Product': 'Another New', 'Price': '0.00'},
        ]
    )
    settings = make_import_settings(create_missing_products=True, email='csv:Email')

    with pytest.raises(DataImportError):
        import_orders.apply(args=(event.pk, cached.id, settings, 'en', user.pk)).get()

    assert event.products.count() == 0


@pytest.mark.django_db
@scopes_disabled()
def test_import_matches_existing_product_by_internal_name(event, user):
    Product.objects.create(
        event=event,
        name=LazyI18nString('Display name'),
        internal_name='vip-internal',
        default_price=Decimal('5.00'),
    )
    cached = make_csv_file([{'Email': 'a@example.com', 'Product': 'vip-internal', 'Price': '0.00'}])
    settings = make_import_settings(create_missing_products=True)

    import_orders.apply(args=(event.pk, cached.id, settings, 'en', user.pk)).get()

    assert event.products.count() == 1
    assert event.orders.count() == 1
