import datetime

import pytest
from django_scopes import scopes_disabled

from eventyay.base.models import Event, Order, OrderPosition, Organizer, Product
from eventyay.plugins.badges.models import BadgeProduct
from eventyay.plugins.badges.utils import get_badge_bundle_option_choices


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
