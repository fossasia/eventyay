from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils.timezone import now
from pytz import UTC

from eventyay.base.models import Product, Quota


@pytest.fixture
def quota(event):
    return Quota.objects.create(event=event, name='Tickets', size=100)


@pytest.fixture
def admission_product(event, quota):
    product = event.products.create(
        name='Open pass',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
    )
    quota.products.add(product)
    return product


@pytest.mark.django_db
def test_device_product_list_hides_expired_admission_products(
    device_client, organizer, event, admission_product
):
    valid_product = event.products.create(
        name='Valid pass',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_FIXED,
        admission_valid_from=now() - timedelta(hours=1),
        admission_valid_until=now() + timedelta(hours=1),
    )
    expired_product = event.products.create(
        name='Expired pass',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_FIXED,
        admission_valid_from=now() - timedelta(days=2),
        admission_valid_until=now() - timedelta(days=1),
    )
    future_product = event.products.create(
        name='Future pass',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_FIXED,
        admission_valid_from=now() + timedelta(days=1),
        admission_valid_until=now() + timedelta(days=2),
    )
    quota = Quota.objects.get(event=event)
    quota.products.add(valid_product, expired_product, future_product)

    resp = device_client.get(f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/products/')
    assert resp.status_code == 200
    product_ids = {entry['id'] for entry in resp.data['results']}
    assert admission_product.pk in product_ids
    assert valid_product.pk in product_ids
    assert expired_product.pk not in product_ids
    assert future_product.pk not in product_ids


@pytest.mark.django_db
def test_token_product_list_keeps_expired_admission_products(token_client, organizer, event, quota):
    expired_product = event.products.create(
        name='Expired pass',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_FIXED,
        admission_valid_from=now() - timedelta(days=2),
        admission_valid_until=now() - timedelta(days=1),
    )
    quota.products.add(expired_product)

    resp = token_client.get(f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/products/')
    assert resp.status_code == 200
    product_ids = {entry['id'] for entry in resp.data['results']}
    assert expired_product.pk in product_ids


@pytest.mark.django_db
def test_device_order_create_rejects_expired_admission_product(device_client, organizer, event, quota):
    expired_product = event.products.create(
        name='Expired pass',
        default_price=Decimal('10.00'),
        admission=True,
        active=True,
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_FIXED,
        admission_valid_from=datetime(2017, 12, 20, 10, 0, 0, tzinfo=UTC),
        admission_valid_until=datetime(2017, 12, 21, 10, 0, 0, tzinfo=UTC),
    )
    quota.products.add(expired_product)

    resp = device_client.post(
        f'/api/v1/organizers/{organizer.slug}/events/{event.slug}/orders/',
        {
            'email': 'walkin@example.test',
            'locale': 'en',
            'sales_channel': 'web',
            'payment_provider': 'manual',
            'send_email': False,
            'invoice_address': {
                'is_business': False,
                'name_parts': {'full_name': 'Walk In'},
                'street': 'N/A',
                'zipcode': '00000',
                'city': 'N/A',
                'country': 'US',
            },
            'positions': [
                {
                    'positionid': 1,
                    'product': expired_product.pk,
                    'attendee_name_parts': {'full_name': 'Walk In'},
                }
            ],
        },
        format='json',
    )
    assert resp.status_code == 400
    assert 'not available for registration' in str(resp.data)
