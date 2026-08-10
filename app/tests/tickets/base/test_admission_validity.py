from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django_scopes import scope
from freezegun import freeze_time

from eventyay.base.admission_validity import (
    assign_issued_admission_bounds,
    get_issued_admission_bounds,
    resolve_catalog_admission_bounds,
)
from eventyay.base.models import (
    CartPosition,
    Checkin,
    Event,
    Order,
    OrderPosition,
    Organizer,
    Product,
)
from eventyay.base.models.product import ProductVariation
from eventyay.base.services.checkin import CheckInError, perform_checkin
from eventyay.base.services.orders import OrderChangeManager


@pytest.fixture
def event():
    o = Organizer.objects.create(name='Dummy', slug='dummy-av')
    event = Event.objects.create(
        organizer=o,
        name='Dummy',
        slug='dummy-av',
        date_from=now() + timedelta(days=1),
        date_to=now() + timedelta(days=1, hours=3),
        plugins='eventyay.plugins.banktransfer',
    )
    event.settings.timezone = 'Europe/Berlin'
    with scope(organizer=o):
        yield event


@pytest.fixture
def item(event):
    return event.products.create(name='Ticket', default_price=3, admission=True)


@pytest.fixture
def clist(event):
    return event.checkin_lists.create(name='Default', all_products=True)


def _make_position(event, item, variation=None, subevent=None, **kwargs):
    order = Order.objects.create(
        code='AV01',
        event=event,
        email='dummy@dummy.test',
        status=Order.STATUS_PAID,
        locale='en',
        datetime=now() - timedelta(days=1),
        expires=now() + timedelta(days=10),
        total=Decimal('23.00'),
    )
    return OrderPosition.objects.create(
        order=order,
        product=item,
        variation=variation,
        subevent=subevent,
        price=Decimal('23.00'),
        attendee_name_parts={'full_name': 'Peter'},
        positionid=1,
        **kwargs,
    )


@pytest.mark.django_db
def test_checkout_transform_cart_positions_snapshots_bounds(event, item):
    start = now() - timedelta(hours=1)
    end = now() + timedelta(hours=2)
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = start
    item.admission_valid_until = end
    item.save()

    order = Order.objects.create(
        code='AVCART',
        event=event,
        email='cart@dummy.test',
        status=Order.STATUS_PENDING,
        locale='en',
        datetime=now(),
        expires=now() + timedelta(days=10),
        total=Decimal('3.00'),
    )
    cartpos = CartPosition.objects.create(
        event=event,
        cart_id='av-cart',
        product=item,
        price=Decimal('3.00'),
        expires=now() + timedelta(hours=1),
    )

    OrderPosition.transform_cart_positions([cartpos], order)
    position = order.positions.get()
    assert position.admission_valid_from == start
    assert position.admission_valid_until == end


@pytest.mark.django_db
def test_order_change_product_resnapshots_bounds(event, item):
    start = now() - timedelta(hours=1)
    end = now() + timedelta(hours=1)
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = start
    item.admission_valid_until = end
    item.save()
    position = _make_position(event, item)

    other = event.products.create(name='Other', default_price=5, admission=True)
    other.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    other.admission_valid_from = now() + timedelta(days=1)
    other.admission_valid_until = now() + timedelta(days=2)
    other.save()
    quota = event.quotas.create(name='Q', size=None)
    quota.products.add(item, other)

    ocm = OrderChangeManager(position.order, None)
    ocm.change_product(position, other, None)
    ocm.commit()
    position.refresh_from_db()
    assert position.admission_valid_from == other.admission_valid_from
    assert position.admission_valid_until == other.admission_valid_until


@pytest.mark.django_db
def test_snapshot_ignores_later_product_changes(event, item):
    start = now() - timedelta(hours=1)
    end = now() + timedelta(hours=1)
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = start
    item.admission_valid_until = end
    item.save()

    position = _make_position(event, item)
    assert position.admission_valid_from == start
    assert position.admission_valid_until == end

    item.admission_valid_from = now() + timedelta(days=5)
    item.admission_valid_until = now() + timedelta(days=6)
    item.save()

    position.refresh_from_db()
    assert get_issued_admission_bounds(position) == (start, end)


@pytest.mark.django_db
def test_empty_snapshot_falls_back_to_current_catalog(event, item):
    position = _make_position(event, item)
    assert get_issued_admission_bounds(position) == (None, None)

    start = now() - timedelta(days=2)
    end = now() - timedelta(days=1)
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = start
    item.admission_valid_until = end
    item.save()

    position.refresh_from_db()
    assert get_issued_admission_bounds(position) == (start, end)


@pytest.mark.django_db
def test_legacy_null_snapshot_uses_catalog_for_checkin(event, item, clist):
    """Positions with empty snapshot fields follow current product validity."""
    position = _make_position(event, item)
    OrderPosition.objects.filter(pk=position.pk).update(
        admission_valid_from=None,
        admission_valid_until=None,
    )
    position.refresh_from_db()

    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = now() - timedelta(days=2)
    item.admission_valid_until = now() - timedelta(days=1)
    item.save()

    with pytest.raises(CheckInError) as excinfo:
        perform_checkin(position, clist, {})
    assert excinfo.value.code == 'invalid_time'


@pytest.mark.django_db
def test_variation_inherits_product_mode_and_overlays_offset(event, item):
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_EVENT
    item.admission_valid_from_offset_minutes = 0
    item.admission_valid_until_offset_minutes = 120
    item.save()
    variation = item.variations.create(
        value='Early',
        admission_validity_mode=ProductVariation.ADMISSION_VALIDITY_MODE_INHERIT,
        admission_valid_from_offset_minutes=30,
    )

    valid_from, valid_until = resolve_catalog_admission_bounds(
        item, variation, event=event, subevent=None
    )
    assert valid_from == event.date_from + timedelta(minutes=30)
    assert valid_until == event.date_from + timedelta(minutes=120)


@pytest.mark.django_db
def test_variation_can_explicitly_clear_product_restriction(event, item):
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = now() - timedelta(hours=1)
    item.admission_valid_until = now() + timedelta(hours=1)
    item.save()
    variation = item.variations.create(
        value='Open',
        admission_validity_mode=Product.ADMISSION_VALIDITY_MODE_NONE,
    )

    assert resolve_catalog_admission_bounds(item, variation, event=event) == (None, None)


@pytest.mark.django_db
def test_negative_offsets_rejected(event):
    with pytest.raises(ValidationError):
        Product.clean_admission_validity(
            Product.ADMISSION_VALIDITY_MODE_EVENT,
            None,
            None,
            offset_from=-10,
            offset_until=30,
            event=event,
        )


@pytest.mark.django_db
def test_offset_cannot_extend_past_event_end(event):
    event_duration_minutes = int((event.date_to - event.date_from).total_seconds() // 60)
    with pytest.raises(ValidationError):
        Product.clean_admission_validity(
            Product.ADMISSION_VALIDITY_MODE_EVENT,
            None,
            None,
            offset_from=0,
            offset_until=event_duration_minutes + 15,
            event=event,
        )


@pytest.mark.django_db
def test_resolved_offsets_are_clamped_to_event_window(event, item):
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_EVENT
    item.admission_valid_from_offset_minutes = 0
    item.save()
    # Bypass clean() to simulate previously stored / imported oversized offset.
    Product.objects.filter(pk=item.pk).update(admission_valid_until_offset_minutes=10_000)
    item.refresh_from_db()

    valid_from, valid_until = resolve_catalog_admission_bounds(item, event=event)
    assert valid_from == event.date_from
    assert valid_until == event.date_to


@pytest.mark.django_db
def test_snapshot_on_create_with_variation_and_subevent(event, item):
    se = event.subevents.create(
        name='Day 1',
        date_from=now() + timedelta(days=2),
        date_to=now() + timedelta(days=2, hours=2),
        active=True,
    )
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_SUBEVENT
    item.save()
    variation = item.variations.create(
        value='Standard',
        admission_validity_mode=ProductVariation.ADMISSION_VALIDITY_MODE_INHERIT,
        admission_valid_from_offset_minutes=15,
    )

    position = _make_position(event, item, variation=variation, subevent=se)
    assert position.admission_valid_from == se.date_from + timedelta(minutes=15)
    assert position.admission_valid_until == se.date_to


@pytest.mark.django_db
def test_assign_issued_bounds_noop_without_order():
    position = SimpleNamespace(product_id=1, product=object(), order=None, variation=None, subevent=None)
    assign_issued_admission_bounds(position)


@pytest.mark.django_db
def test_checkin_allows_exact_boundaries(event, item, clist):
    start = now().replace(microsecond=0)
    end = start + timedelta(hours=2)
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = start
    item.admission_valid_until = end
    item.save()
    position = _make_position(event, item)

    with freeze_time(start):
        perform_checkin(position, clist, {})
    assert position.checkins.count() == 1

    position.checkins.all().delete()
    with freeze_time(end):
        perform_checkin(position, clist, {})
    assert position.checkins.count() == 1


@pytest.mark.django_db
def test_checkin_rejects_outside_window_but_force_bypasses(event, item, clist):
    start = now() + timedelta(hours=1)
    end = now() + timedelta(hours=2)
    item.admission_validity_mode = Product.ADMISSION_VALIDITY_MODE_FIXED
    item.admission_valid_from = start
    item.admission_valid_until = end
    item.save()
    position = _make_position(event, item)

    with pytest.raises(CheckInError) as excinfo:
        perform_checkin(position, clist, {})
    assert excinfo.value.code == 'invalid_time'

    perform_checkin(position, clist, {}, force=True)
    assert position.checkins.count() == 1


@pytest.mark.django_db
def test_checkin_no_restriction(event, item, clist):
    position = _make_position(event, item)
    perform_checkin(position, clist, {})
    assert position.checkins.filter(type=Checkin.TYPE_ENTRY).count() == 1


def test_pdf_font_fallback_prefers_and_before_transliteration():
    from eventyay.base.pdf import resolve_textarea_font

    open_sans = mock.Mock()
    open_sans.face.charToGlyph = {}
    and_font = mock.Mock()
    and_font.face.charToGlyph = {ord(c): 1 for c in 'こんにちは'}

    def _get(name):
        if name.startswith('AND'):
            return and_font
        return open_sans

    with (
        mock.patch('eventyay.base.pdf.pdfmetrics.getFont', side_effect=_get),
        mock.patch('text_unidecode.unidecode') as unidecode,
    ):
        font, text = resolve_textarea_font('Open Sans', 'こんにちは')
        assert font == 'AND'
        assert text == 'こんにちは'
        unidecode.assert_not_called()


def test_pdf_font_fallback_transliterates_only_as_last_resort():
    from eventyay.base.pdf import resolve_textarea_font

    open_sans = mock.Mock()
    open_sans.face.charToGlyph = {ord(c): 1 for c in 'konnichiha'}
    and_font = mock.Mock()
    and_font.face.charToGlyph = {}

    def _get(name):
        if name.startswith('AND'):
            return and_font
        return open_sans

    with (
        mock.patch('eventyay.base.pdf.pdfmetrics.getFont', side_effect=_get),
        mock.patch('text_unidecode.unidecode', return_value='konnichiha') as unidecode,
    ):
        font, text = resolve_textarea_font('Open Sans', 'こんにちは')
        assert font == 'Open Sans'
        assert text == 'konnichiha'
        unidecode.assert_called_once_with('こんにちは')
