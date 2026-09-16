from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from django_scopes import scopes_disabled

from eventyay.base.models import CartPosition, Event, Organizer, Quota
from eventyay.base.models.product import Product, ProductAddOn, ProductBundle, ProductCategory
from eventyay.base.services.cart import CartManager

CART_ID = 'voucher-included-test'


@pytest.fixture
def setup(db):
    organizer = Organizer.objects.create(name='Org', slug='voucherorg')
    event = Event.objects.create(
        organizer=organizer,
        name='Event',
        slug='voucherevent',
        date_from=timezone.now() + timedelta(days=10),
        currency='EUR',
        live=True,
    )
    with scopes_disabled():
        ticket = Product.objects.create(event=event, name='Ticket', default_price=Decimal('23.00'))
        workshops = ProductCategory.objects.create(event=event, name='Workshops', is_addon=True)
        workshop = Product.objects.create(
            event=event, name='Workshop', category=workshops, default_price=Decimal('12.00')
        )
        transport = Product.objects.create(
            event=event, name='Transport', default_price=Decimal('2.50'), require_bundling=True
        )
        quota = Quota.objects.create(event=event, name='Quota', size=10)
        quota.products.add(ticket, workshop, transport)
        ProductAddOn.objects.create(base_product=ticket, addon_category=workshops)
        ProductBundle.objects.create(
            base_product=ticket, bundled_product=transport, designated_price=Decimal('1.50'), count=1
        )
        yield event, ticket, workshop, transport


def _add_ticket(event, ticket, voucher=None):
    cm = CartManager(event=event, cart_id=CART_ID)
    item = {'product': ticket.pk, 'variation': None, 'count': 1}
    if voucher:
        item['voucher'] = voucher.code
    cm.add_new_products([item])
    cm.commit()
    return CartPosition.objects.get(cart_id=CART_ID, addon_to__isnull=True)


def test_bundle_keeps_designated_price_without_option(setup):
    event, ticket, _, _ = setup
    with scopes_disabled():
        voucher = event.vouchers.create(code='PLAIN', product=ticket)
        cp = _add_ticket(event, ticket, voucher)
        bundled = cp.addons.get(is_bundled=True)
        assert cp.price == Decimal('21.50')
        assert bundled.price == Decimal('1.50')


def test_all_bundles_included_makes_bundles_free(setup):
    event, ticket, _, _ = setup
    with scopes_disabled():
        voucher = event.vouchers.create(code='BUNDLE', product=ticket, all_bundles_included=True)
        cp = _add_ticket(event, ticket, voucher)
        bundled = cp.addons.get(is_bundled=True)
        assert cp.price == Decimal('23.00')
        assert bundled.price == Decimal('0.00')


def test_all_addons_included_makes_addons_free(setup):
    event, ticket, workshop, _ = setup
    with scopes_disabled():
        voucher = event.vouchers.create(code='ADDON', product=ticket, all_addons_included=True)
        cp = _add_ticket(event, ticket, voucher)
        cm = CartManager(event=event, cart_id=CART_ID)
        cm.set_addons([{'addon_to': cp.pk, 'product': workshop.pk, 'variation': None}])
        cm.commit()
        addon = cp.addons.get(is_bundled=False)
        assert addon.price == Decimal('0.00')


def test_addons_charged_without_option(setup):
    event, ticket, workshop, _ = setup
    with scopes_disabled():
        cp = _add_ticket(event, ticket)
        cm = CartManager(event=event, cart_id=CART_ID)
        cm.set_addons([{'addon_to': cp.pk, 'product': workshop.pk, 'variation': None}])
        cm.commit()
        addon = cp.addons.get(is_bundled=False)
        assert addon.price == Decimal('12.00')


def test_apply_voucher_later_frees_existing_addons_and_bundles(setup):
    event, ticket, workshop, _ = setup
    with scopes_disabled():
        cp = _add_ticket(event, ticket)
        cm = CartManager(event=event, cart_id=CART_ID)
        cm.set_addons([{'addon_to': cp.pk, 'product': workshop.pk, 'variation': None}])
        cm.commit()
        voucher = event.vouchers.create(
            code='BOTH', product=ticket, all_addons_included=True, all_bundles_included=True
        )
        cm = CartManager(event=event, cart_id=CART_ID)
        cm.apply_voucher(voucher.code)
        cm.commit()
        cp.refresh_from_db()
        assert cp.voucher == voucher
        assert cp.price == Decimal('23.00')
        assert all(a.price == Decimal('0.00') for a in cp.addons.all())
