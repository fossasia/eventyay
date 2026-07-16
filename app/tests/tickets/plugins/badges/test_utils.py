import datetime

import pytest
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product, Voucher
from eventyay.base.pdf import Renderer
from eventyay.plugins.badges.models import BadgeProduct, BadgeVoucher
from eventyay.plugins.badges.utils import (
    get_badge_bundle_option_choices,
    get_badge_layout_for_position,
    position_has_printable_badge,
)


@pytest.fixture
def badge_event():
    with scopes_disabled():
        organizer = Organizer.objects.create(name='CCC', slug='ccc')
        event = Event.objects.create(
            organizer=organizer,
            name='30C3',
            slug='30c3',
            plugins='eventyay.plugins.badges',
            date_from=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
        )
        product = Product.objects.create(event=event, name='Standard', default_price=0, position=1)
        order = Order.objects.create(
            event=event,
            email='dummy@dummy.test',
            status='p',
            datetime=datetime.datetime(2013, 12, 26, tzinfo=datetime.timezone.utc),
            expires=datetime.datetime(2014, 1, 26, tzinfo=datetime.timezone.utc),
            total=0,
        )
        position = OrderPosition.objects.create(
            order=order,
            product=product,
            price=0,
            attendee_name_parts={},
            secret='1234',
        )
        layout = event.badge_layouts.create(
            name='Layout 1',
            default=True,
            allow_customization=True,
            ask_user_fields_data=['attendee_name'],
        )
        yield event, position, product, layout


@pytest.mark.django_db
def test_badge_options_hidden_without_product_layout_assignment(badge_event):
    event, position, product, layout = badge_event

    assert get_badge_bundle_option_choices(event, position) == []


@pytest.mark.django_db
def test_badge_options_shown_with_product_layout_assignment(badge_event):
    event, position, product, layout = badge_event
    BadgeProduct.objects.create(product=product, layout=layout)

    choices = get_badge_bundle_option_choices(event, position)

    assert len(choices) == 1
    assert choices[0][0] == 'attendee_name'


@pytest.mark.django_db
def test_badge_options_hidden_when_product_explicitly_has_no_layout(badge_event):
    event, position, product, layout = badge_event
    BadgeProduct.objects.create(product=product, layout=None)

    assert get_badge_bundle_option_choices(event, position) == []


@pytest.mark.django_db
def test_voucher_explicit_assignment_enables_checkout_options(badge_event):
    event, position, product, layout = badge_event
    voucher = Voucher.objects.create(event=event, code='VOUCHER3')
    position.voucher = voucher
    position.save(update_fields=['voucher'])
    BadgeVoucher.objects.create(voucher=voucher, layout=layout)

    choices = get_badge_bundle_option_choices(event, position)

    assert len(choices) == 1
    assert choices[0][0] == 'attendee_name'


@pytest.mark.django_db
def test_voucher_layout_overrides_product_default(badge_event):
    event, position, product, layout = badge_event
    voucher_layout = event.badge_layouts.create(name='Voucher layout')
    voucher = Voucher.objects.create(event=event, code='VOUCHER1')
    position.voucher = voucher
    position.save(update_fields=['voucher'])

    BadgeVoucher.objects.create(voucher=voucher, layout=voucher_layout)

    assert get_badge_layout_for_position(event, position) == voucher_layout
    assert position_has_printable_badge(event, position) is True


@pytest.mark.django_db
def test_voucher_layout_none_disables_badge_even_with_default_product(badge_event):
    event, position, product, layout = badge_event
    voucher = Voucher.objects.create(event=event, code='VOUCHER2')
    position.voucher = voucher
    position.save(update_fields=['voucher'])

    BadgeVoucher.objects.create(voucher=voucher, layout=None)

    assert get_badge_layout_for_position(event, position) is None
    assert position_has_printable_badge(event, position) is False


def test_fit_fontsize_to_width_shrinks_unbreakable_text():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'VeryLongAttendeeNameExample',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted < 12.0
    assert fitted >= 4.0


def test_fit_fontsize_to_width_keeps_wrappable_text_at_max():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'Very Long Attendee Name Example',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted == 12.0


def test_fit_fontsize_to_width_keeps_short_text_at_max():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'Ann',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted == 12.0


def test_fit_fontsize_to_width_multiline_uses_longest_line():
    Renderer._register_fonts()
    fitted = Renderer._fit_fontsize_to_width(
        'John\nDoe',
        'Open Sans',
        max_fontsize=12.0,
        width_mm=30,
    )

    assert fitted == 12.0
